# Retrieval and the module chatbots

How each module grounds its assistant, why there is no vector database, and where the real
accuracy limits are. Written to be quotable in the report — every number below is from the code
or measured on this machine.

---

## 1. The governing principle

**Retrieval is a compression strategy for context that does not fit. If it fits, do not retrieve.**

Every retrieval step can miss. A passage that is relevant but ranks seventh when you take six is
simply gone, and the model answers without it, confidently. So retrieval is only worth its risk
when the alternative — putting everything in the prompt — is impossible.

That principle is why the three modules ground their chatbots differently, and the differences
are deliberate rather than historical:

| Module | Grounding | Why |
|---|---|---|
| **Desk research** | Vector retrieval over document chunks | A session holds far more text than any context window. Retrieval is unavoidable. |
| **Social listening** | **Injects the whole report**; retrieval only as a safety valve above 40,000 characters | A report fits. Injecting it cannot miss. |
| **Interview guide** | **Injects the whole guide**, plus the prior ORION self-assessment *only* when the question is about cross-referencing it | The guide fits; the assessment transcript is added conditionally to keep ordinary questions lean. |

Two of the three modules therefore do no retrieval at all in the normal case. This is a feature.

---

## 2. Why there is no vector database

A vector database is not storage for documents — the documents, their extracted text, their
passages and their vectors all live in object storage regardless. A vector database would replace
only the *search*.

**What the search is.** The embedding model turns any text into 384 numbers. A session of 300
passages is therefore a 300 x 384 matrix — 0.4 MB, stored as one `.npy` file. Answering a question
is one line (`store.py`):

```python
sims = vecs @ qv              # both normalised, so this IS cosine similarity
top = np.argsort(-sims)[:k]
```

**Measured on the deployment machine:**

| Passages | Matrix | Search |
|---:|---:|---:|
| 300 | 0.4 MB | 0.01 ms |
| 1,000 | 1.5 MB | 0.05 ms |
| 10,000 | 14.6 MB | 0.62 ms |
| 100,000 | 147 MB | 6.97 ms |
| 1,000,000 | 1.5 GB | 88.8 ms |

A real session searches in a hundredth of a millisecond, and only one session's matrix is ever
loaded — each session is its own namespace, and queries never cross sessions.

**What a vector database would add** is *approximate* nearest-neighbour search (HNSW, IVF): skip
most vectors, accept a small chance of missing the true best match. That is an excellent trade at
a million vectors. At three hundred it is a bad one on every axis:

- **Slower** — a network hop to another service costs 1-5 ms, which is 100x the search it replaces.
- **Less accurate** — see below.
- **More to operate** — another service to deploy, secure, back up and pay for.

**The accuracy point is the one usually missed:** brute-force cosine is *exact*. It is the ground
truth that approximate indexes are measured against. Choosing not to use a vector database does
not cost recall — it guarantees 100% of it. Any accuracy concern about this system lies elsewhere.

The upgrade path, if the corpus ever outgrows this, is `pgvector` — vector search inside the
Postgres already running — not a new service.

---

## 3. Where the accuracy limits actually are

Ranked by how much each one costs, most first.

### 3.1 No reranking stage — the biggest available gain

Retrieval returns the top *k* by embedding similarity and stops. There is no cross-encoder
rerank pass over a wider candidate set.

This matters because bi-encoders (which embed query and passage separately, as here) are fast but
coarse; a cross-encoder reads the query and passage *together* and scores far more accurately.
The standard pattern is to retrieve ~30 cheaply and rerank to 6. In published retrieval
benchmarks that step typically buys more than upgrading the embedding model does.

**This is the highest-value improvement available, and it is not implemented.**

### 3.2 The embedding model is the smallest of its family

`intfloat/multilingual-e5-small` — 384 dimensions, roughly 118M parameters. `e5-base` (768d) and
`e5-large` (1024d) score measurably higher on retrieval benchmarks, and the gap is wider for
multilingual content (Arabic, French) than for English, which is exactly this corpus.

So yes: **the model is a real accuracy limit.** It is also a defensible trade:

- it runs on CPU inside the existing container, so there is no embedding API cost and **no client
  document ever leaves the machine**;
- a larger local model costs RAM, which is already the binding constraint (see the sizing section
  in `TECHNICAL.md`);
- it is used *correctly*, which matters more than size in practice.

That last point deserves stating, because it is the usual failure: e5 models are trained with
`query:` and `passage:` prefixes and collapse in quality without them. This code applies both
(`embeddings.py`) and normalises the vectors so the dot product is a true cosine. The most common
way to break this model is not present here.

### 3.3 No relevance floor

`RAG_MIN_SCORE` defaults to `0.0`, so the top *k* are returned regardless of how weak the match
is. The comment in `store.py` explains the reasoning: e5 similarity scores are compressed
(relevant ~0.80-0.88, unrelated ~0.72), so an absolute cutoff is brittle and would silently drop
good hits.

The cost is that "nothing relevant exists" and "here are six mediocre passages" look identical to
the answering step. The mitigation is a prompt instructed to decline when the context does not
contain the answer — which is a softer guarantee than a threshold would be.

### 3.4 Chunking is reasonable but untuned

Sentences packed to ~900 characters with a one-sentence overlap between chunks. That is a sane
default. It has not been tuned against this corpus, and table-heavy documents — common here —
usually want different handling from prose.

### 3.5 What partly compensates: multi-query planning

Before retrieving, a planner rewrites the user's question into several queries and retrieves for
each, merging the results. This meaningfully offsets a weaker embedding model, because a passage
missed by one phrasing is often caught by another. It is real machinery, already in place.

---

## 4. Honest summary for the report

- **The absence of a vector database costs nothing in accuracy.** Exhaustive cosine search is
  exact; approximate indexes are what trade accuracy for speed. The decision is scale-appropriate,
  and the measured search time leaves roughly two orders of magnitude of headroom.
- **The embedding model is the weakest component**, and it is a deliberate trade of some semantic
  precision for zero cost, zero data egress and low memory. It is at least implemented correctly.
- **The largest untaken improvement is a reranking stage**, not a vector database and not a bigger
  embedding model.
- **Two of the three chatbots do not retrieve at all**, which sidesteps the question entirely:
  when the whole report or guide fits in the prompt, injecting it is strictly more reliable than
  retrieving from it.
- The RAG surface is **genuinely small** in this product — it is one feature of one module, plus a
  fallback path in another. Engineering it as though it were the core of the system would have
  been misallocated effort.

---

## 5. Reference

| Setting | Value | Where |
|---|---|---|
| Embedding model | `intfloat/multilingual-e5-small` (384d) | `RAG_EMBED_MODEL` |
| Prefixes | `query: ` / `passage: ` | `embeddings.py` |
| Vectors | normalised; cosine == dot product | `embeddings.py` |
| Index | numpy matrix per namespace, `.npy` in object storage | `store.py` |
| Chunk size | ~900 chars, 1-sentence overlap | `chunker.py` |
| Top-k | 6 (12 for the social fallback) | `store.py`, `social_chat.py` |
| Relevance floor | `0.0` (disabled) | `RAG_MIN_SCORE` |
| Social injection ceiling | 40,000 chars before falling back to RAG | `social_chat.py` |
| Fallback when embeddings unavailable | lexical keyword overlap over the same chunks | `store.py` |
| Reranking | none | — |
