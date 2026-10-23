"""Test isolation. Imported by pytest before any test module, so this runs first.

**Why this file exists.** There was no pytest configuration at all, and
``app.core.config.get_settings()`` calls ``load_env_file()``, which does
``load_dotenv(override=True)`` on ``backend/.env``. That file holds *production* credentials, so
simply running ``pytest`` locally pointed the suite at the production database and the production
object storage — several tests were writing to it. That is a correctness problem (tests that
depend on remote state are flaky) and a safety problem (a test run mutating production).

**How it is fixed.** Two steps, in this order:

1. Environment variables are set at import time, before anything imports ``app.*``.
2. ``load_env_file`` is replaced with a no-op, because ``override=True`` would otherwise put the
   production values straight back. The settings cache is cleared so nothing built earlier
   survives.

The production code is untouched — the neutralisation lives entirely here, so there is no way for
it to change how the deployed application loads its configuration.

**The guard.** ``_refuse_production`` fails the run outright if the resulting configuration still
points at something that looks like production. A silent fallback would recreate exactly the
problem this file was written to remove.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# --------------------------------------------------------------------------------------------
# 1. A safe environment, set before app modules are imported
# --------------------------------------------------------------------------------------------

_TEST_ROOT = Path(tempfile.gettempdir()) / "cx_studio_tests"
_TEST_ROOT.mkdir(parents=True, exist_ok=True)

_TEST_ENV = {
    # Local disk, never the hosted bucket.
    "STORAGE_BACKEND": "disk",
    "RAG_DATA_ROOT": str(_TEST_ROOT / "rag_data"),
    # Obviously-not-production placeholders. Nothing in the suite should reach a real database;
    # a test that needs one must stand up its own.
    "DATABASE_URL": "postgresql+asyncpg://test:test@127.0.0.1:5432/cx_test",
    "APP_ENV": "development",
    "JWT_SECRET": "test-only-secret-not-used-anywhere-real",
    # Blank every provider credential. A unit test must never spend money or depend on a remote
    # service being up; anything needing a provider has to inject a fake.
    "MISTRAL_API_KEY": "",
    "GEMINI_API_KEYS": "",
    "OPENROUTER_API_KEY": "",
    "OPENAI_API_KEY": "",
    "MOONSHOT_API_KEY": "",
    "APIFY_API_TOKEN": "",
    "BRIGHTDATA_API_TOKEN": "",
    "LANGSEARCH_API_KEY": "",
    "SUPABASE_URL": "",
    "SUPABASE_SERVICE_KEY": "",
    "SUPABASE_BUCKET": "",
    "LANGFUSE_PUBLIC_KEY": "",
    "LANGFUSE_SECRET_KEY": "",
    # No outbound mail from a test run.
    "SMTP_HOST": "",
    "EMAIL_FROM": "",
}

for _key, _value in _TEST_ENV.items():
    os.environ[_key] = _value


# --------------------------------------------------------------------------------------------
# 2. Stop the application putting production values back
# --------------------------------------------------------------------------------------------

from app.core import config as _config  # noqa: E402  (must follow the env setup above)


def _no_op_load_env_file() -> None:
    """Replaces the real loader for the duration of the test session.

    The real one calls ``load_dotenv(..., override=True)``, which would overwrite everything set
    above with the contents of the production ``.env``.
    """


_config.load_env_file = _no_op_load_env_file
_config.get_settings.cache_clear()


# --------------------------------------------------------------------------------------------
# 3. Fail loudly if any of that did not take
# --------------------------------------------------------------------------------------------

_PRODUCTION_MARKERS = ("supabase.co", "supabase.com", "pooler.supabase")


def _refuse_production() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    storage = os.getenv("STORAGE_BACKEND", "")
    supabase = os.getenv("SUPABASE_URL", "")

    for marker in _PRODUCTION_MARKERS:
        if marker in database_url or marker in supabase:
            raise pytest.UsageError(
                f"Test isolation failed: configuration still points at production ({marker!r}). "
                "Refusing to run — a test run must never read or write the live system."
            )
    if storage != "disk":
        raise pytest.UsageError(
            f"Test isolation failed: STORAGE_BACKEND is {storage!r}, expected 'disk'."
        )


_refuse_production()


@pytest.fixture(scope="session", autouse=True)
def isolated_storage_root(tmp_path_factory):
    """A per-session scratch directory for anything that still writes relative paths.

    Several stores build paths like ``scraped_data/chats`` relative to the working directory.
    Running from a temporary directory keeps those out of the repository.
    """
    root = tmp_path_factory.mktemp("cx_studio")
    previous = Path.cwd()
    os.chdir(root)
    try:
        yield root
    finally:
        os.chdir(previous)
