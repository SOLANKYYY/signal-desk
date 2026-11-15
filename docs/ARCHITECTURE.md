# Architecture

## Application boundaries

| Component | Main files | Responsibility |
| --- | --- | --- |
| Web adapter | `app.py`, `backend/web.py` | Flask routes, shared-account login, same-origin writes, response streaming |
| Intelligence | `backend/intelligence.py` | Feed ingestion, stored events and observations, provenance and search |
| Assistant | `backend/chat.py` | Provider configuration, source validation, embeddings, retrieval, memory, metrics |
| Local AI host | `backend/chat_app.py`, `appendix-a/` | FastAPI host plus shared Flask UI, local MongoDB and Ollama |
| Report pipeline | `backend/ingest.py`, `backend/pdf_worker.py`, `backend/cloud.py`, `worker.py` | Catalog ingestion and queued PDF processing |
| Investigation | `backend/investigation.py`, `backend/alerts.py` | Case records, analyst notes, rule-based attention levels |
| Coursework | `backend/coursework.py`, `backend/replica_lab.py`, `backend/exercise9.py` | Validate, store, and display uploaded experimental evidence |
| Browser | `frontend/` | Source interface assets; `scripts/vercel_build.py` copies assets to ignored `public/` |

## Assistant data flow

1. Authenticate the shared application account.
2. Validate the source excerpt, original HTTPS URL, scope, and any analyst assessment.
3. Split text into 200-word passages with a 40-word overlap; embed with the configured model.
4. Store normalized vectors and provenance in `chat_chunks`. The embedding space includes provider, model, and dimensions.
5. Embed the question and apply scope/embedding-space filters before ranking up to three passages.
6. Supply retrieved text as untrusted evidence with the last five completed exchanges to the selected model.
7. Emit sources and answer events through the application's NDJSON response. Gemini generation uses a complete native API response; OpenAI/Ollama support provider streaming.
8. Save a completed question/answer pair and its sources atomically. Failures are displayed, not recorded as successful answers.

## MongoDB collections

| Collection | Contents |
| --- | --- |
| `threat_events` | Publisher feed-event metadata |
| `threat_records` | Indicator observations associated with feed events |
| `chat_chunks` | Evidence passages, embeddings, provenance, scope |
| `chat_turns` | Completed exchanges by shared account and session UUID |
| `chat_limits` | Per-account request counters with expiry |
| `chat_locks` | Prevent simultaneous answers in one conversation |
| `chat_metrics` | Attempt outcome, latency, token usage; expires after 30 days |
| `coursework_evidence` | Imported lab output and checksums |
| `exercise9_runs` | Separate chapter 9 evidence |

Report-processing collections are described in the technical guide. Lab import endpoints do not execute Docker or change production topology.

## Retrieval modes

`exact` loads and ranks at most 3,000 matching chunks with cosine similarity in Python. `atlas` uses MongoDB `$vectorSearch` and requires an appropriate index. Neither mode silently substitutes for the other. Similarity is not a probability that a claim is true.

The supplied `appendix-a/vector-index.json` uses 1536 dimensions for OpenAI. Configure 3072 for Gemini embedding-001 or 768 for the bundled Ollama model. Re-import evidence after changing the embedding space.

## Security model

Hosted requests use signed, HttpOnly cookies or authenticated API access. The login represents one shared account; conversation UUIDs are not separate user identities. Provider credentials remain on the server. Source content is escaped in the browser and is not executed. The model has no tools for scanning, patching, or changing devices. See the security policy for operating boundaries.
