"""Guards for chat-history persistence and the report being retrievable by the agent."""

from __future__ import annotations

import numpy as np
import pytest

from app.schemas.desk_research import StoredChatMessage
from app.services import storage
from app.services.desk_research import rag_index, session_manager
from app.services.rag import store


class _FakeEmbedder:
    available = True
    _VOCAB = ["risk", "peak", "load", "revenue", "churn", "findings"]

    def _vec(self, text):
        low = text.lower()
        v = np.array([float(low.count(w)) for w in self._VOCAB], dtype=np.float32)
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed_passages(self, texts):
        return np.vstack([self._vec(t) for t in texts]).astype(np.float32)

    def embed_query(self, text):
        return self._vec(text)


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Point all storage at a temp directory, and stub the embedder.

    Sessions and the RAG index both write through `app.services.storage`, so swapping the one
    backend isolates both. This used to patch `_DATA_ROOT` and `_RAG_ROOT` as filesystem paths;
    they are storage KEY PREFIXES now, and patching them stopped isolating anything.
    """
    monkeypatch.setattr(storage, "_backend", storage.DiskBackend(tmp_path))
    monkeypatch.setattr(store, "get_embedder", lambda: _FakeEmbedder())


def test_chat_history_persists_and_reloads():
    sess = session_manager.create_session()
    sid = sess.session_id
    session_manager.append_chat(sid, [
        StoredChatMessage(id="1", role="user", text="What is the service level?", ts=1.0),
        StoredChatMessage(id="2", role="assistant", text="It was 55.1%.", sources=["acme.pdf, p1"], ts=2.0),
    ])
    # A second turn appends, not overwrites.
    session_manager.append_chat(sid, [StoredChatMessage(id="3", role="user", text="And in 2025?", ts=3.0)])

    loaded = session_manager.load_chat(sid)
    assert [m.id for m in loaded] == ["1", "2", "3"]
    assert loaded[1].sources == ["acme.pdf, p1"]

    # get_session surfaces the history so the frontend restores it on reload.
    info = session_manager.get_session(sid)
    assert len(info.messages) == 3 and info.messages[0].text == "What is the service level?"


def test_generated_report_is_indexed_and_retrievable():
    sess = session_manager.create_session()
    sid = sess.session_id
    ns = rag_index.namespace_for(sid)

    session_manager.save_report(
        sid,
        "# Executive Report\n\n## Findings\nRevenue grew and churn improved.\n\n## Risks\nPeak load instability is the top risk.",
    )
    rag_index.rebuild_index(sid)  # with no documents, only the report is indexed

    hits = store.query_index(ns, "peak load risk", k=3)
    assert hits, "the report should be retrievable"
    assert any(h.chunk.source_name == rag_index.REPORT_SOURCE_NAME for h in hits)
    assert any("Peak load" in h.chunk.text for h in hits)
