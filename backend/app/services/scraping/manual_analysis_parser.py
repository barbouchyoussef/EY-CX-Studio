"""Parses the consultant-filled 'Social Media & Website Analysis' Excel template
(backend/app/static/templates/SM_Website_Analysis_TEMPLATE.xlsx) into structured data.

The template intentionally leaves most cells optional (see the 'Read Me' tab), so every
read here is defensive: missing sheets, missing cells, and stray formula errors are
collected as warnings instead of raising.
"""

from __future__ import annotations

import io
import logging

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from app.schemas.manual_analysis import (
    ChannelAnalysis,
    ChannelPost,
    ManualAnalysisParseResponse,
    ManualAnalysisWorkbook,
    ThemeInsight,
    WebsiteAnalysis,
    WebsiteTraffic,
)

logger = logging.getLogger(__name__)

_CHANNEL_SHEETS = ["LinkedIn", "Facebook", "Instagram", "X (ex Twitter)"]

_METRIC_COLUMNS = {
    "followers_growth": "C",
    "page_verification": "D",
    "engagement_rate": "E",
    "post_interaction_rate": "F",
    "response_time_to_comments": "G",
    "response_quality": "H",
    "posting_frequency": "I",
    "content_format_variety": "J",
    "campaign": "K",
    "complaints_handling": "L",
    "resolution_effectiveness": "M",
    "sentiment_analysis": "N",
}

_POST_LOG_FIRST_ROW = 12
_POST_LOG_LAST_ROW = 26
_THEME_FIRST_ROW = 6
_THEME_LAST_ROW = 24

# Unlike the channel tabs (where the example lives in a separate, clearly-labelled
# "Example" row below the blank input row), the Themes & Insights example rows are the
# literal first two data rows (6 and 7). Consultants are told they "may delete" them but
# nothing forces it, and simply typing over a cell in Excel keeps its italic/green
# formatting -- so font styling can't reliably distinguish an edited row from an
# untouched example. Instead we skip a row only if it is byte-for-byte the shipped
# example text, which a real finding would essentially never coincidentally match.
_EXAMPLE_THEME_SIGNATURES = {
    ("Delivery & Shipping", "Customers repeatedly report late deliveries and no proactive updates on delays."),
    ("Product Quality", "Fabric quality and durability are the most praised aspect, driving repeat purchases."),
}

# A row can be a genuine new finding (theme/description edited) while still leaving
# stale example text behind in columns the consultant never touched -- those individual
# values are stripped even when the row itself is kept.
_EXAMPLE_EXAMPLES_TEXT = {
    '"3rd order that arrives a week late, no notification" · "Where is my parcel? Nobody replies."',
    '"Still looks new after a year" · "Best quality for the price, I keep coming back"',
}
_EXAMPLE_INTERPRETATION_TEXT = {
    "Fulfilment & delivery-comms drive the most negative sentiment — prioritise SLA + tracking notifications.",
    "Quality is a genuine strength and loyalty driver — lean on it in messaging and reviews.",
}

# Same problem on the Website tab: the traffic figures and section names are literal
# example values living directly in the input cells, with no separate example row.
_EXAMPLE_WEBSITE_TRAFFIC = {
    "total_visits": "929",
    "desktop_share": "2.55%",
    "mobile_share": "97.45%",
    "pages_per_visit": "1.43",
    "bounce_rate": "47.77%",
    "avg_visit_duration": "e.g. 00:01:32",
}
_EXAMPLE_WEBSITE_SECTIONS = {"e.g. Personal", "e.g. Business", "e.g. Services", "e.g. Support", "e.g. About"}


def _clean_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _display_value(ws: Worksheet, coord: str) -> str | None:
    """Read a cell that may hold free text, a number, or a percentage and return it as
    human-readable text (e.g. a 0.024-fraction percentage cell becomes '2.4%')."""
    cell = ws[coord]
    value = cell.value
    if value is None:
        return None
    if isinstance(value, (int, float)) and cell.number_format and "%" in cell.number_format:
        return f"{value * 100:.1f}%"
    return _clean_str(value)


def _to_number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace("%", "").strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _parse_read_me(ws: Worksheet, warnings: list[str]) -> tuple[str | None, str | None, str | None]:
    company = _clean_str(ws["C3"].value)
    period = _clean_str(ws["C4"].value)
    analyst = _clean_str(ws["C5"].value)
    if not company:
        warnings.append("No company name found on the 'Read Me' tab (cell C3).")
    return company, period, analyst


def _parse_channel(ws: Worksheet, channel_name: str) -> ChannelAnalysis:
    metrics = {field: _display_value(ws, f"{col}7") for field, col in _METRIC_COLUMNS.items()}

    posts: list[ChannelPost] = []
    for row in range(_POST_LOG_FIRST_ROW, _POST_LOG_LAST_ROW + 1):
        date = _clean_str(ws[f"B{row}"].value)
        post_name = _clean_str(ws[f"C{row}"].value)
        likes = _to_number(ws[f"D{row}"].value)
        comments = _to_number(ws[f"E{row}"].value)
        shares = _to_number(ws[f"F{row}"].value)
        notes = _clean_str(ws[f"H{row}"].value)
        if not any((date, post_name, likes, comments, shares, notes)):
            continue
        total = sum(v for v in (likes, comments, shares) if v is not None)
        posts.append(
            ChannelPost(
                date=date,
                post=post_name,
                likes=likes,
                comments=comments,
                shares=shares,
                total_engagement=total,
                notes=notes,
            )
        )

    def _avg(values: list[float | None]) -> float | None:
        present = [v for v in values if v is not None]
        return round(sum(present) / len(present), 2) if present else None

    notes_cell = _clean_str(ws["B32"].value)

    return ChannelAnalysis(
        channel=channel_name,
        account_handle=_clean_str(ws["C3"].value),
        posts=posts,
        avg_likes=_avg([p.likes for p in posts]),
        avg_comments=_avg([p.comments for p in posts]),
        avg_shares=_avg([p.shares for p in posts]),
        avg_engagement=_avg([p.total_engagement for p in posts]),
        notes=notes_cell,
        **metrics,
    )


def _parse_website(ws: Worksheet) -> WebsiteAnalysis:
    url = _clean_str(ws["C3"].value)
    sections = [
        s
        for s in (_clean_str(ws[f"{col}8"].value) for col in "BCDEF")
        if s and s not in _EXAMPLE_WEBSITE_SECTIONS
    ]

    traffic_coords = {
        "total_visits": "D17",
        "desktop_share": "D18",
        "mobile_share": "D19",
        "pages_per_visit": "D20",
        "bounce_rate": "D21",
        "avg_visit_duration": "D22",
    }
    traffic_values = {}
    for field, coord in traffic_coords.items():
        value = _display_value(ws, coord)
        traffic_values[field] = None if value == _EXAMPLE_WEBSITE_TRAFFIC[field] else value

    return WebsiteAnalysis(url=url, sections=sections, traffic=WebsiteTraffic(**traffic_values))


def _parse_themes(ws: Worksheet) -> list[ThemeInsight]:
    themes: list[ThemeInsight] = []
    raw_counts: list[int] = []

    for row in range(_THEME_FIRST_ROW, _THEME_LAST_ROW + 1):
        theme_name = _clean_str(ws[f"B{row}"].value)
        if not theme_name:
            continue
        description = _clean_str(ws[f"E{row}"].value)
        if (theme_name, description) in _EXAMPLE_THEME_SIGNATURES:
            continue
        opinions_raw = _to_number(ws[f"F{row}"].value)
        opinions_count = int(opinions_raw) if opinions_raw is not None else None
        if opinions_count:
            raw_counts.append(opinions_count)

        examples = _clean_str(ws[f"H{row}"].value)
        if examples in _EXAMPLE_EXAMPLES_TEXT:
            examples = None
        interpretation = _clean_str(ws[f"I{row}"].value)
        if interpretation in _EXAMPLE_INTERPRETATION_TEXT:
            interpretation = None

        themes.append(
            ThemeInsight(
                theme=theme_name,
                type=_clean_str(ws[f"C{row}"].value),
                source=_clean_str(ws[f"D{row}"].value),
                description=description,
                opinions_count=opinions_count,
                examples=examples,
                interpretation=interpretation,
            )
        )

    total = sum(raw_counts)
    if total > 0:
        for theme in themes:
            if theme.opinions_count:
                theme.share_of_mentions = round(theme.opinions_count / total, 3)

    return themes


def parse_manual_analysis_workbook(file_bytes: bytes) -> ManualAnalysisParseResponse:
    warnings: list[str] = []

    try:
        wb = load_workbook(io.BytesIO(file_bytes), data_only=True)
    except Exception as exc:
        logger.warning("Failed to open uploaded manual-analysis workbook: %s", exc)
        raise ValueError(
            "Could not open this file as an Excel workbook. Please upload the .xlsx template."
        ) from exc

    company_name = period = analyst = None
    if "Read Me" in wb.sheetnames:
        company_name, period, analyst = _parse_read_me(wb["Read Me"], warnings)
    else:
        warnings.append("The 'Read Me' tab is missing, so company name/period/analyst could not be read.")

    channels: list[ChannelAnalysis] = []
    for sheet_name in _CHANNEL_SHEETS:
        if sheet_name not in wb.sheetnames:
            warnings.append(f"'{sheet_name}' tab is missing, skipped.")
            continue
        try:
            channel = _parse_channel(wb[sheet_name], sheet_name)
        except Exception as exc:
            logger.warning("Failed to parse channel sheet '%s': %s", sheet_name, exc)
            warnings.append(f"Could not fully read the '{sheet_name}' tab.")
            continue
        if channel.has_any_data():
            channels.append(channel)

    website = None
    if "Website" in wb.sheetnames:
        try:
            parsed_website = _parse_website(wb["Website"])
            if parsed_website.has_any_data():
                website = parsed_website
        except Exception as exc:
            logger.warning("Failed to parse Website sheet: %s", exc)
            warnings.append("Could not fully read the 'Website' tab.")

    themes: list[ThemeInsight] = []
    if "Themes & Insights" in wb.sheetnames:
        try:
            themes = _parse_themes(wb["Themes & Insights"])
        except Exception as exc:
            logger.warning("Failed to parse Themes & Insights sheet: %s", exc)
            warnings.append("Could not fully read the 'Themes & Insights' tab.")
    else:
        warnings.append("The 'Themes & Insights' tab is missing.")

    if not channels and not website and not themes:
        warnings.append("No filled-in data was found anywhere in the workbook.")

    workbook = ManualAnalysisWorkbook(
        company_name=company_name,
        reporting_period=period,
        analyst=analyst,
        channels=channels,
        website=website,
        themes=themes,
    )
    return ManualAnalysisParseResponse(workbook=workbook, warnings=warnings)
