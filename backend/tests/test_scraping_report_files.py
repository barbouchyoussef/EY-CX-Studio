"""The report filename is untrusted input; these lock down where it can reach the filesystem.

The name is chosen by the browser and travels with every report request. Two things changed since
this file was first written, and both matter:

  * **Report lookup no longer touches the filesystem.** Reports moved into
    ``scraping_jobs.result``, and the name is now matched by a parameterised SQL comparison
    (``app/api/routes/scraping.py``). The old ``_resolve_report_path`` guard went with it, which
    is why the previous version of this module failed to import and — because pytest aborts the
    whole run on a collection error — blocked the entire suite.

  * **One filesystem path survives**: the per-report chat log, keyed by that same name. That is
    now the only place an attacker-controlled string reaches ``os.path.join``, so it is what
    these tests cover.

The assertion is deliberately a *containment property* rather than an expected string. Path
semantics differ between the Windows dev machine and the Linux container (a backslash is a
separator on one and an ordinary character on the other), so "the resolved path never leaves the
chats directory" is the claim that holds on both.
"""

from __future__ import annotations

import os

import pytest

from app.services.scraping.report_chat import _CHATS_DIR, _chat_path


def _stays_inside(path: str) -> bool:
    """True when *path* resolves inside the chats directory."""
    root = os.path.abspath(_CHATS_DIR)
    return os.path.commonpath([root, os.path.abspath(path)]) == root


def test_a_normal_report_name_lands_in_the_chats_directory():
    path = _chat_path("mytek_report_20260721_215723.json")
    assert _stays_inside(path)
    assert os.path.basename(path) == "mytek_report_20260721_215723.json"


@pytest.mark.parametrize(
    "attack",
    [
        "../../../etc/passwd",
        "../../app/main.py",
        "..\\..\\app\\core\\config.py",
        "/etc/shadow",
        "C:\\Windows\\System32\\config\\SAM",
        "....//....//secrets.json",
        "../../../../deploy.env",
    ],
)
def test_traversal_attempts_cannot_escape_the_chats_directory(attack):
    """Whatever the name looks like, the resolved path stays under the chats directory."""
    assert _stays_inside(_chat_path(attack))


def test_a_traversal_disguised_as_a_report_name_still_cannot_escape():
    assert _stays_inside(_chat_path("../../x_report_1.json"))


def test_the_name_never_contributes_a_directory_component():
    """The guard is basename(): the result is always a single file directly in the chats dir."""
    path = _chat_path("../../../etc/passwd")
    assert os.path.dirname(os.path.abspath(path)) == os.path.abspath(_CHATS_DIR)
