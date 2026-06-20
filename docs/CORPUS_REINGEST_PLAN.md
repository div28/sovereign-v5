# Corpus Re-Ingest Plan (v2 indexes)

Status: **planned, not executed.** Saved for later pickup. Do not touch the live
Pinecone indexes or `INDEX_REGISTRY` until the cutover step is explicitly approved.

## Why

Grounding (`clause_grounded` / `clause_source`) is live on all 9 judges but only
delivers traceable citations for SOX, not GDPR. Read-only diagnostics traced this
to the **corpus**, not the matcher:

1. **No clause metadata (all frameworks).** Every vector has empty
   `metadata.article` / `metadata.section`. Ingestion chunked by fixed ~500-token
   windows (`start_token`/`end_token`/`chunk_index`) with no article-tagging step,
   so the strong (metadata) clause-match path is dead everywhere. SOX only grounds
   via the weak *text* fallback (confidence 0.85, never 1.0).
2. **GDPR OCR mangling (GDPR-specific).** GDPR text has intra-word spaces
   ("Ar ticle 22", "par ticular", "prof iling") — classic PyPDF2/pdfminer artifact
   on a justified PDF. So even the text fallback fails: the literal string
   "Article 22" does not exist in the GDPR chunks. This is why **GDPR = 0%** while
   **SOX = 100%**.
3. **Retrieval gap (scenario-specific).** For a broad scenario query the actual
   Article 22 body is not in the top-15; a targeted query retrieves it at much
   higher scores (~0.64–0.69 vs ~0.24–0.30).

The original ingestion script is **not in the repo** (ran once, off-repo). The
re-ingest below rebuilds the corpus correctly into **new v2 indexes**, proves it
fixes grounding without hurting detection, then cuts over atomically.

## Source PDFs (recovered)

Located at `/Users/divya288/sovereign-v2/data/regulations/`:

| Framework | Path |
|---|---|
| GDPR | `gdpr/GDPR_Regulation_2016-679.pdf` |
| SOX | `sox/Sarbanes_Oxley_Act_2002.pdf` |
| EU-AI | `eu-ai-act/EU_AI_Act_2024.pdf` |

(HIPAA/CCPA/EEOC PDFs also exist there but are **out of scope** — no judges.)

Step 1 of execution copies these into the repo at `data/regulations/{gdpr,sox,euai}/`
and commits them (version-control the corpus). Confirm no `.gitignore` excludes
`data/` first.

## Embedding model (must not change)

`text-embedding-3-small`, **1536 dimensions** (`backend/rag/embeddings.py`). Re-embed
with the SAME model so v2 indexes are dimensionally compatible and retrieval scores
stay comparable.

## Index topology

Live indexes (read by the backend via `backend/rag/pinecone_client.py`
`INDEX_REGISTRY`), default namespace `""`:

| Framework | Live index | Vectors | Dim |
|---|---|---|---|
| gdpr | `sovereign-gdpr-regulation` | 219 | 1536 |
| sox | `sovereign-sox-regulation` | 121 | 1536 |
| euai | `sovereign-euai-regulation` | 39 | 1536 |

v2 index spec (match the live `sovereign-gdpr-regulation`):

```
metric:    cosine
dimension: 1536
spec:      serverless { cloud: aws, region: us-east-1 }
```

New index names: `sovereign-{framework}-regulation-v2`. **Do not** upsert into the
live indexes; build v2 alongside.

## Ingestion script design — `scripts/ingest_corpus.py` (new, committed)

Parameterized by `--framework` + `--index` so SOX/EU-AI reuse it later. Pilot run
targets **GDPR → `sovereign-gdpr-regulation-v2` only**.

1. **Extract** text with **PyMuPDF (`fitz`)** — primary; pdfplumber as fallback.
   Requires `pip install pymupdf tiktoken` (add to `requirements.txt`).
2. **Validate clean text** before chunking: assert "Article 22" (GDPR) /
   "Section 404" (SOX) appear contiguous, and **reject if intra-word artifacts
   exist** (e.g. `"Ar ticle"` count > 0). Fall back to pdfplumber on failure.
3. **Article/section-aware chunking:** detect `^Article N` / `^Section N` headings,
   segment by clause, and **stamp `metadata.article` / `metadata.section` on every
   chunk**. Sub-split long clauses to **≤ ~500 tokens** (tiktoken `cl100k_base`),
   carrying the clause label onto each sub-chunk.
4. **Metadata schema** must match what `backend/rag/retriever.py` reads
   (`article`, `section`, `title`, `source`, `page`, `chunk_index`, `framework`,
   plus `text`) so `metadata.article="22"` flows into the strong clause-match path.
5. **Embed** with `embeddings.embed_batch` (same model, 1536).
6. **Upsert** to the v2 index (create if missing, spec above). Deterministic IDs
   (e.g. `gdpr-art{N}-{chunk_index}` + content hash) for idempotent re-runs.

## Verification (offline, GDPR, against v2 — live untouched)

A verification script (does NOT change `INDEX_REGISTRY`):

1. Confirm the **Article 22 body chunk exists with `metadata.article="22"`** and is
   **retrievable** from v2 (semantic query by index name directly).
2. Re-run the **grounding check** (FraudShield + GDPR golden scenarios): pull chunks
   **from v2**, feed them to the real judges via
   `judge.evaluate(submission, retrieved_chunks=<v2 chunks>)`, and report per finding
   `clause_grounded`, `clause_source.chunk_id` (real v2 id), `match` (expect
   `metadata`), `grounding_confidence`.
3. Confirm **detection still fires** on the GDPR golden scenarios (no regression).

**Acceptance — show before/after:**
- `clause_grounded` rate: live **0/6** → v2 **expected 6/6 via metadata**.
- detection: every GDPR scenario still `violation_detected=True` at expected severity.

## Cutover (separate, approval-gated — NOT part of the GDPR pilot)

1. After GDPR v2 verification passes, get approval.
2. Ingest **SOX** and **EU-AI** into `sovereign-sox-regulation-v2` /
   `sovereign-euai-regulation-v2` with the same script; verify each.
3. **Atomic switch:** change the three names in `INDEX_REGISTRY`
   (`backend/rag/pinecone_client.py`) from `…-regulation` to `…-regulation-v2`,
   commit, deploy. The backend keys off these names, so production is untouched until
   the flip; **instant rollback** = revert the names.
4. Leave the old `…-regulation` indexes in place until v2 is confirmed healthy in
   production, then delete them to reclaim quota.

## Risks

- **IDs change** (new corpus → new vector IDs). No live code depends on specific
  IDs; historical `clause_source.chunk_id` / stored `retrieved_context` become
  stale (cosmetic).
- **Do not upsert into live indexes.** New IDs would coexist with the old 219/121/39
  vectors (upsert overwrites by ID; new IDs don't collide) → doubled index, mixed
  retrieval. Always build v2 separately.
- **Env change:** `pip install pymupdf tiktoken` + add to `requirements.txt` (not a
  Pinecone/live change).
- **Cost:** ~220 GDPR chunks × 1 embed = negligible; writes go only to v2.
- Re-ingest is reversible while it stays on v2 indexes — if grounding doesn't
  improve, don't flip `INDEX_REGISTRY`.
