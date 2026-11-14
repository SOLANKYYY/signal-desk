# Final assessment: Signal Desk Threat Assistant

**Solanki Om Narendra | 24BTRCL190 | 5AIMLB | 23CSE528**

Reference: https://github.com/sujeetjagtap/NoSQL-Databases-using-MongoDB/tree/main/appendix-a

Live workspace: https://signal-desk-xi-seven.vercel.app/#assistant

Current source repository: https://github.com/SOLANKYYY/signal-desk

## What this adds to Signal Desk

The existing project has public threat feeds, original source links, report/PDF evidence, investigation notes, file/message checks, database comparisons, and a coursework hub for experiments 11-18 with separate Docker links. The hub records imported evidence; it does not independently rerun those experiments. Earlier labs remain in `/laboratory`.

The new Threat Assistant connects these ideas into a retrieval-augmented chat workflow. It embeds evidence using a real model, retrieves three matching chunks, streams an LLM answer with source references, and saves the completed exchange and its source excerpts in MongoDB. It includes the last five completed exchanges in follow-up prompts. It does not use the reference implementation's deterministic random mock embeddings.

The interface supports Windows, Linux, macOS, Android and iOS, plus unknown/all. It supports anticipated, active, evolving and resolved threats, plus unassessed/all. These are analyst-supplied lifecycle assessments. The application never infers infection, exploitation or resolution from a feed date. A specific lifecycle stage requires a written evidence basis; imported feed events default to unknown platform and unassessed stage.

## Requirements map

| Assignment item | Implementation | Verification boundary |
| --- | --- | --- |
| A.1 LLM or SLM | OpenAI hosted API or local Ollama; streamed provider output | Real model run requires a configured provider |
| A.2 Chunk, embed, store | 200-word chunks, 40-word overlap, real embeddings, idempotent source replacement | Provider calls isolated in unit tests; no fabricated vectors in runtime |
| A.3 RAG API | Authenticated `/api/assistant/chat` on Vercel; Docker FastAPI `/chat` and `/ingest` plus integrated UI | NDJSON stream: sources, token events, completion or error |
| A.4 Conversation memory | `chat_turns` documents scoped to account and session UUID, last five exchanges | Shared app account is one user identity; no claim of separate visitor accounts |
| A.5 Chat frontend | Existing blue-and-white workspace, filters, citations, conversation resume, source ingestion | Safe text rendering; incomplete responses are explicitly marked |
| A.6 Container stack | MongoDB + Ollama + FastAPI/Flask integrated frontend | Docker engine is not available in this editing environment; run locally |
| A.7 Hardening | Existing login, bounded requests, same-origin writes, atomic rate limits, metrics, health endpoint, shutdown cleanup | Local Compose is loopback-only HTTP and isolated MongoDB; use HTTPS/TLS before remote hosting |

## Architecture and storage

1. An authenticated analyst adds an excerpt and its original HTTPS URL, or selects stored feed events.
2. The server validates title, text, platform and stage assessment. It records the URL without fetching it.
3. The embedding provider returns real vectors; dimensions and finite non-zero values are checked.
4. MongoDB `chat_chunks` stores provenance, content, scope, model space and normalized embeddings.
5. A question is embedded with the same model; platform, stage and embedding-space filters apply before retrieval.
6. Retrieved chunks and the last five exchanges are passed to the LLM as untrusted context, with a defensive system instruction. No execution tools exist.
7. Provider tokens stream to the browser. One complete question/answer pair and its citations are stored atomically in `chat_turns` only after successful generation. Failed partial output is not saved as a completed answer.
8. `chat_metrics` records latency, success/error and provider-reported token counts. The UI shows the last 24 hours; metrics expire after 30 days. Conversation and evidence records persist until explicitly managed by the owner.

Additional collections: `chat_limits` uses atomic increments per account/minute with a TTL index; `chat_locks` prevents overlapping requests in the same conversation. Limits are 12 chat attempts and five ingestion batches per minute. Maximum question length is 2,000 characters. One batch accepts up to five documents and 40 chunks. Provider credentials stay in server environment variables.

## Option A: use the existing Vercel website

In Vercel > Signal Desk > Settings > Environment Variables, configure:

| Variable | Value |
| --- | --- |
| `LLM_BACKEND` | `openai` |
| `OPENAI_API_KEY` | Your own API key, entered privately in Vercel |
| `OPENAI_MODEL` | `gpt-4o-mini` (default; may be overridden with a compatible Chat Completions model) |
| `EMBEDDING_MODEL` | `text-embedding-3-small` |
| `EMBEDDING_DIMENSIONS` | `1536` |
| `CHAT_RETRIEVAL` | `exact` initially, or `atlas` after creating the index below |

Keep the existing APP_USERNAME, APP_PASSWORD, MONGODB_URI and MONGODB_DB. Redeploy after changing environment variables. Open Threat Assistant, add evidence, then ask a question. API usage can incur provider charges. Questions, selected evidence and the last five exchanges are sent to the configured provider; do not enter private incident data or secrets.

No model key was available to the implementation agent. A configured status is not a successful live model test. A live end-to-end answer must still be demonstrated with your provider.

### Atlas Vector Search

Create a `vectorSearch` index on the existing application's **chat_chunks** collection, named **chat_vector_index**, using `appendix-a/vector-index.json`. Its vector field is `embedding`, with 1536 dimensions and cosine similarity; filter fields are `space`, `platform` and `stage`. Wait until the index is queryable, then set CHAT_RETRIEVAL=atlas and redeploy. Do not create it on threat_events.

The supplied index matches OpenAI's default embedding size. For Ollama nomic-embed-text use 768 dimensions instead. Re-ingest evidence when changing embedding models. The `space` identifier prevents vectors from incompatible models being mixed.

Exact mode loads at most 3,000 matching chunks from MongoDB and ranks cosine similarities in Python. It is a valid local reference workflow but **is not Atlas indexed vector search**. It refuses larger candidate sets instead of silently sampling them. Atlas mode never silently falls back to exact search. Similarity is not a confidence or correctness probability.

## Option B: local Docker with Ollama, no API key

From the repository root in Windows PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\appendix-a\START.ps1
```

The script creates a random local password in ignored `appendix-a/.env`, starts services, downloads llama3.2:3b and nomic-embed-text, and builds the app. Allow several GB of disk space. Stop unused lab containers if RAM is limited; do not delete their volumes. Open **http://localhost:8019/#assistant**. Username is `admin`; read your generated password from the local `.env` privately. The first local startup imports the bundled, provenance-documented public feed snapshot into the dedicated `signal_desk_final` database; it does not overwrite the cloud database.

Only port 8019 is bound to the host, on loopback. MongoDB and Ollama are accessible by service name inside the Compose network. MongoDB authentication/TLS is not enabled for this isolated local lab stack. Never expose its network services remotely without adding authentication and TLS. The deployed Vercel site uses HTTPS; use an Atlas SRV/TLS connection for cloud MongoDB.

Stop without deleting data:

```powershell
docker compose -f .\appendix-a\compose.yml stop
```

Restart:

```powershell
docker compose -f .\appendix-a\compose.yml up -d
```

Health: `http://localhost:8019/health` checks MongoDB, not model readiness. The FastAPI lifespan closes the shared MongoClient during shutdown. The embedded Flask site keeps existing authenticated pages, while `/chat` and `/ingest` accept the same account credentials using Basic Authentication for API clients. Their responses do not trigger browser password popups.

## Demonstration and evidence to capture

1. Open Threat Assistant. Capture configured model, retrieval mode and chunk count.
2. Add three to five real advisory/report excerpts with original source URLs. Choose a platform. Use unassessed unless the source supports a lifecycle assessment. Capture the non-zero chunk result.
3. Ask a question whose answer is present in an excerpt. Capture the streamed answer and expand citations to compare the actual retrieved text and URL.
4. Ask a follow-up that depends on the previous exchange. Switch away and reopen/resume the conversation. Capture the stored history.
5. Change platform/stage filters. Demonstrate an empty scope returns an explicit no-evidence message, not an invented answer.
6. Restart the local app container and reopen the same conversation. Capture persistence. If using Vercel, document the equivalent new browser session/resume test.
7. Capture real request latency, token use and errors from the monitoring panel. Do not substitute example timings or mocked test outputs for model measurements.
8. If Atlas mode is used, capture the queryable search index and the UI's atlas retrieval label.

The optional background device-scanning and remediation bot is not implemented. The assistant does not run shell commands, patch machines, or claim to scan devices. Existing file signature/hash/message checks remain separate features.

## Verification performed by the implementation agent

94 Python tests passed, including 17 assistant tests covering batch ingestion, real-vector validation, idempotence, filters, conversation isolation, history bounds, streaming persistence, missing configuration, error behavior, rate limiting, feed provenance, Atlas pipeline filters, and authenticated HTTP contracts. Two frontend state checks verify the configured/unconfigured assistant UI and escaping. The model and MongoDB are mocked in automated tests; this is not live AI or Docker execution evidence. See the repository tests for reproducible assertions.

## Submission: private repository, PDF and faculty access

GitHub reported **SOLANKYYY/signal-desk is public** during this update. The assignment explicitly asks for a PRIVATE GitHub repository. Do not claim that the current public URL satisfies that requirement. The connected GitHub integration does not expose repository-visibility or collaborator administration in this session.

Choose one of these on GitHub yourself:

- Change this repository to private in Settings > General > Danger Zone > Change repository visibility; verify Vercel's GitHub integration retains access.
- Or create a separate private final-assessment repository and copy the tracked source, Docker files and docs into it. Keep the production repository unchanged.

Invite the faculty GitHub account under Settings > Collaborators. Confirm the actual account with the faculty; no collaborator invitation was sent by the implementation agent. GitHub user names are not inferred from a display name.

The final PDF should include your name/USN/class, the **verified private repository URL**, architecture, requirements mapping, actual screenshots, measured model results, source citations, limitations and conclusion. Never include `.env`, API keys, passwords, database exports containing private data, or Docker credential files. The implementation-status PDF supplied with this update clearly labels these outstanding demonstration and submission steps.

## References

- Faculty instructions: Instructions_LLM-based Chat Application.docx.pdf (six pages supplied in this chat).
- Appendix A source: https://github.com/sujeetjagtap/NoSQL-Databases-using-MongoDB/tree/main/appendix-a
- OpenAI Chat Completions: https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create
- OpenAI embeddings: https://developers.openai.com/api/reference/resources/embeddings/methods/create
- Ollama API: https://docs.ollama.com/api
- MongoDB Vector Search: https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-stage/
