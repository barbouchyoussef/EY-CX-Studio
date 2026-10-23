"""Report generation recovers from incomplete or incorrectly shaped model output."""

import asyncio
import json

import pytest

from app.services.scraping import social_report_service as service


VALID = json.dumps({
    "executive_summary": "Summary from supplied evidence.",
    "methodology_note": "Based on scraped reviews.",
})


def generate(monkeypatch, responses):
    calls = []
    answers = iter(responses)

    class Gateway:
        async def chat_messages(self, messages):
            calls.append(messages)
            return next(answers)

    monkeypatch.setattr(service, "get_settings", lambda: object())
    monkeypatch.setattr(service, "build_mistral_gateway", lambda _: Gateway())
    result = asyncio.run(service.generate_detailed_social_report("Brand", []))
    return result, calls


@pytest.mark.parametrize("invalid", [
    '{"text": "Staff professionalism"}',
    '{"top_strengths": [{"text": "Staff professionalism"}],',
    'No JSON returned',
    '{"executive_summary": [], "methodology_note": "Scraped"}',
    # Even a schema-valid nested object must not rescue a truncated outer report.
    '{"unexpected_nested_object": ' + VALID,
])
def test_invalid_response_is_regenerated(monkeypatch, invalid):
    report, calls = generate(monkeypatch, [invalid, VALID])
    assert report.executive_summary == "Summary from supplied evidence."
    assert report.evidence is not None
    assert len(calls) == 2
    assert calls[1][:2] == calls[0]
    assert "previous response failed validation" in calls[1][-1]["content"]


@pytest.mark.parametrize("response", [VALID, '```json\n' + VALID + '\n```'])
def test_complete_report_needs_no_retry(monkeypatch, response):
    report, calls = generate(monkeypatch, [response])
    assert report is not None
    assert len(calls) == 1


def test_retries_are_bounded(monkeypatch):
    report, calls = generate(monkeypatch, ['{"text": "Wrong shape"}'] * 3)
    assert report is None
    assert len(calls) == 3
