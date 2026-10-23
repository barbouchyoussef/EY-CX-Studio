"""One storage interface, two interchangeable backends (the adapter pattern).

The app calls ``storage.put_bytes(key, data)`` / ``get_text(key)`` / ``exists(key)`` etc. and does
NOT know whether the bytes live on the local disk or in Supabase object storage. Which backend
answers is chosen once, by the ``STORAGE_BACKEND`` env var:

    STORAGE_BACKEND=disk       -> local filesystem (dev; fast, free, no network)  [default]
    STORAGE_BACKEND=supabase   -> Supabase Storage over HTTP (production; persistent)

Why an adapter instead of calling Supabase directly everywhere:
- local development keeps working on disk with zero credentials and zero network;
- production gets durable storage that survives restarts/redeploys;
- swapping to a different provider (e.g. Cloudflare R2) later changes THIS file only.

A "key" is a flat string like ``desk/<session_id>/originals/report.pdf``. There are no real
folders in object storage — the slashes are just part of the name. The disk backend maps a key to
a real path under a root dir so the same keys work in both worlds.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#  The interface every backend implements                                     #
# --------------------------------------------------------------------------- #
class StorageBackend:
    """The operations the app needs — the same five ideas as the disk code it replaces:
    write, read, exists, list, delete (one key, or a whole prefix)."""

    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> None: ...
    def get_bytes(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def list_keys(self, prefix: str) -> list[str]: ...
    def delete(self, key: str) -> None: ...
    def delete_prefix(self, prefix: str) -> None: ...

    # Text helpers (JSON / markdown) built on the bytes primitives — every backend gets these free.
    def put_text(self, key: str, text: str) -> None:
        self.put_bytes(key, text.encode("utf-8"), content_type="text/plain; charset=utf-8")

    def get_text(self, key: str) -> str:
        return self.get_bytes(key).decode("utf-8")


# --------------------------------------------------------------------------- #
#  Backend 1 — local disk (dev). This is essentially your current code,        #
#  centralised so nothing else needs to touch the filesystem directly.         #
# --------------------------------------------------------------------------- #
class DiskBackend(StorageBackend):
    def __init__(self, root: str | Path):
        self._root = Path(root)

    def _path(self, key: str) -> Path:
        return self._root / key

    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)  # object storage has no folders; disk does
        p.write_bytes(data)

    def get_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def list_keys(self, prefix: str) -> list[str]:
        base = self._path(prefix)
        if not base.exists():
            return []
        root = self._root
        return sorted(
            str(p.relative_to(root)).replace("\\", "/")
            for p in base.rglob("*") if p.is_file()
        )

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            p.unlink()

    def delete_prefix(self, prefix: str) -> None:
        p = self._path(prefix)
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()


# --------------------------------------------------------------------------- #
#  Backend 2 — Supabase Storage over its REST API (production).                #
#  Same interface; the difference is HTTP calls to Supabase instead of disk.   #
#  Uses the SERVICE key (server-side only, never shipped to the browser).      #
# --------------------------------------------------------------------------- #
class SupabaseBackend(StorageBackend):
    def __init__(self, url: str, service_key: str, bucket: str):
        self._base = f"{url.rstrip('/')}/storage/v1"
        self._bucket = bucket
        self._headers = {"Authorization": f"Bearer {service_key}", "apikey": service_key}
        # A short timeout is fine for small files; report/doc uploads are modest.
        self._client = httpx.Client(timeout=30.0)

    @staticmethod
    def _enc(key: str) -> str:
        # Percent-encode the key for the URL path, keeping '/' as the separator. Object keys can
        # contain spaces and non-ASCII (e.g. Arabic filenames), which must not go raw into a URL.
        return quote(key, safe="/")

    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> None:
        # upsert=true so re-writing the same key overwrites (matches disk write semantics).
        r = self._client.post(
            f"{self._base}/object/{self._bucket}/{self._enc(key)}",
            content=data,
            headers={**self._headers,
                     "Content-Type": content_type or "application/octet-stream",
                     "x-upsert": "true"},
        )
        r.raise_for_status()

    def get_bytes(self, key: str) -> bytes:
        r = self._client.get(f"{self._base}/object/{self._bucket}/{self._enc(key)}", headers=self._headers)
        r.raise_for_status()
        return r.content

    def exists(self, key: str) -> bool:
        # A HEAD via the info endpoint; 200 => present, 404 => absent.
        r = self._client.get(f"{self._base}/object/info/{self._bucket}/{self._enc(key)}", headers=self._headers)
        return r.status_code == 200

    def list_keys(self, prefix: str) -> list[str]:
        # Supabase list is per-prefix and non-recursive; we page/recurse to gather all files.
        out: list[str] = []
        stack = [prefix.rstrip("/")]
        while stack:
            cur = stack.pop()
            r = self._client.post(
                f"{self._base}/object/list/{self._bucket}",
                headers={**self._headers, "Content-Type": "application/json"},
                json={"prefix": f"{cur}/" if cur else "", "limit": 1000,
                      "sortBy": {"column": "name", "order": "asc"}},
            )
            r.raise_for_status()
            for item in r.json():
                name = item.get("name")
                if not name:
                    continue
                child = f"{cur}/{name}" if cur else name
                # A folder-like entry has no id/metadata; recurse into it.
                if item.get("id") is None and item.get("metadata") is None:
                    stack.append(child)
                else:
                    out.append(child)
        return sorted(out)

    def delete(self, key: str) -> None:
        self._client.delete(f"{self._base}/object/{self._bucket}/{self._enc(key)}", headers=self._headers)

    def delete_prefix(self, prefix: str) -> None:
        keys = self.list_keys(prefix)
        if keys:
            # Bulk remove via the API's "prefixes" delete.
            self._client.request(
                "DELETE",
                f"{self._base}/object/{self._bucket}",
                headers={**self._headers, "Content-Type": "application/json"},
                json={"prefixes": keys},
            )


# --------------------------------------------------------------------------- #
#  Pick the backend once, from the environment.                               #
# --------------------------------------------------------------------------- #
def _build_backend() -> StorageBackend:
    kind = os.getenv("STORAGE_BACKEND", "disk").lower()
    if kind == "supabase":
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_SERVICE_KEY", "")
        bucket = os.getenv("SUPABASE_BUCKET", "cx-files")
        if not url or not key:
            raise RuntimeError("STORAGE_BACKEND=supabase but SUPABASE_URL / SUPABASE_SERVICE_KEY are unset")
        logger.info("storage: using Supabase backend (bucket=%s)", bucket)
        return SupabaseBackend(url, key, bucket)
    root = os.getenv("STORAGE_DISK_ROOT", ".")
    logger.info("storage: using disk backend (root=%s)", root)
    return DiskBackend(root)


# Built lazily on FIRST USE, not at import — so a storage misconfig (e.g. STORAGE_BACKEND=supabase
# with a missing key) surfaces as a clear error on the first storage call, and does NOT crash the
# whole app at startup (which would take down login and the frontend too).
_backend: StorageBackend | None = None

def _get() -> StorageBackend:
    global _backend
    if _backend is None:
        _backend = _build_backend()
    return _backend


# Module-level functions the app calls (delegating to the chosen backend).
def put_bytes(key: str, data: bytes, content_type: str | None = None) -> None:
    _get().put_bytes(key, data, content_type)

def get_bytes(key: str) -> bytes:
    return _get().get_bytes(key)

def put_text(key: str, text: str) -> None:
    _get().put_text(key, text)

def get_text(key: str) -> str:
    return _get().get_text(key)

def exists(key: str) -> bool:
    return _get().exists(key)

def list_keys(prefix: str) -> list[str]:
    return _get().list_keys(prefix)

def delete(key: str) -> None:
    _get().delete(key)

def delete_prefix(prefix: str) -> None:
    _get().delete_prefix(prefix)
