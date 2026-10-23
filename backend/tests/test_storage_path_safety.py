"""Storage keys stay inside their prefix, and the client link path cannot be steered.

The disk backend resolves a key as ``root / key``, which walks straight out of the root when
given ``../``. Nothing reached that, but only because every desk-research route resolves its
session through ``_session_or_404`` first and a traversal id matches no session -- a guard doing
this job by accident, which stops working the moment a route reads before it resolves.

These tests assert the property directly instead: an id that could leave the prefix is refused
where the key is built, so no caller can get it wrong.
"""

from __future__ import annotations

import inspect

import pytest

from app.services.desk_research import session_manager


# Ids that must keep working. Sessions are uuid4().hex[:16] today, but fixtures and benchmarks
# created sessions named things like "audit_sess", and those directories still exist.
VALID_IDS = ["49a37083837d4995", "audit_sess", "benchmark_sess_1", "a", "A-b_c.d"]

TRAVERSAL_IDS = [
    "..",
    ".",
    "../../etc/passwd",
    "..\\..\\windows\\win.ini",
    "a/b",
    "a\\b",
    "/etc/passwd",
    "",
    "x\x00y",
]

KEY_BUILDERS = [
    session_manager._session_prefix,
    session_manager._meta_key,
    session_manager._chat_key,
    session_manager._processed_prefix,
    session_manager._originals_prefix,
]


@pytest.mark.parametrize("session_id", VALID_IDS)
@pytest.mark.parametrize("builder", KEY_BUILDERS, ids=lambda b: b.__name__)
def test_real_session_ids_still_build_keys(builder, session_id):
    key = builder(session_id)
    assert key.startswith(session_manager._ROOT + "/")
    assert session_id in key


@pytest.mark.parametrize("bad", TRAVERSAL_IDS)
@pytest.mark.parametrize("builder", KEY_BUILDERS, ids=lambda b: b.__name__)
def test_traversal_ids_are_refused(builder, bad):
    with pytest.raises(ValueError):
        builder(bad)


@pytest.mark.parametrize("bad", TRAVERSAL_IDS)
def test_document_ids_are_refused_too(bad):
    """doc_id is a separate path parameter and reaches the key the same way."""
    with pytest.raises(ValueError):
        session_manager._processed_key("49a37083837d4995", bad)


def test_an_unsafe_session_id_reads_as_not_found():
    """Every route resolves a session through get_session, so this is what turns a hostile id
    into a 404 rather than a 500."""
    assert session_manager.get_session("../../etc/passwd") is None
    assert session_manager.get_session("..") is None


def test_uploaded_filenames_cannot_escape_their_session():
    """Display names are preserved on the document; the storage key is slugged to ASCII."""
    for hostile in ["../../evil.pdf", "..\\..\\evil.pdf", "/etc/passwd.pdf"]:
        safe = session_manager._safe_object_name(hostile)
        assert "/" not in safe and "\\" not in safe and ".." not in safe


def test_upload_route_bounds_the_read():
    """save_original enforces the size limit, but only once the file is already a bytes object.
    The route must cap the read itself so an oversized upload is never materialised."""
    from app.api.routes import desk_research

    source = inspect.getsource(desk_research.upload_files)
    assert "read(session_manager.MAX_FILE_SIZE_BYTES + 1)" in source, (
        "upload_files must read at most one byte beyond the limit, so an oversized file is "
        "rejected rather than loaded into memory"
    )


def test_respondent_routes_take_no_assessment_id_from_the_caller():
    """The passwordless client path has no IDOR surface by construction: the assessment is
    whatever the link token resolves to, and no route accepts an id to override it."""
    from app.main import app

    offenders = []
    for route in app.routes:
        if not hasattr(route, "dependant") or not route.path.startswith("/api/v1/respondent"):
            continue
        if "{" in route.path:
            offenders.append(f"{route.path} takes a path parameter")
        source = inspect.getsource(route.endpoint)
        if "body.assessment_id" in source:
            offenders.append(f"{route.path} reads an assessment id from the body")
    assert not offenders, "; ".join(offenders)
