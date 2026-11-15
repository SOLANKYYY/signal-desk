# Getting started

Choose one entrypoint; the repository supports different environments deliberately.

| Environment | Entrypoint | Address | Database/model |
| --- | --- | --- | --- |
| Online workspace | Vercel `app.py` | Owner's Vercel domain | Atlas and hosted provider |
| Full local AI stack | `appendix-a/START.ps1` | `localhost:8019` | Docker MongoDB + Ollama |
| Flask development | `python -m flask --app app run --host 127.0.0.1 --port 8000` | `localhost:8000` | Configure database and provider |
| Older report service | `python -m backend.server` | `localhost:8000` | Local MongoDB; keep private |

Follow the root README for installation commands. Root `docker-compose.yml` starts only MongoDB. The Appendix A Compose file starts the complete model stack and has separate data volumes. Do not run destructive volume cleanup to resolve ordinary connection errors.

## Online Gemini configuration

Set these in Vercel project environment settings, with keys stored as Secrets. Use a Google project on the free API tier with billing disabled if no spending is intended.

```text
LLM_BACKEND=gemini
GEMINI_MODEL=gemini-3.1-flash-lite
GEMINI_API_KEY=<private key>
EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_DIMENSIONS=3072
CHAT_RETRIEVAL=exact
```

Also configure `MONGODB_URI`, `MONGODB_DB`, `APP_USERNAME`, `APP_PASSWORD` (16+ characters), and `CRON_SECRET` (32+ characters). Redeploy after changing variables. API credentials are separate from consumer chat subscriptions. Verify model availability and quotas in the provider console; no paid fallback is automatic.

Open AI Chatbot → Evidence library. Import one public feed report or paste a full advisory excerpt, then ask a question with both filters on All. Feed summaries contain metadata, not the full publisher article. The supplied source URL is recorded rather than fetched by chat ingestion.

## Optional providers

| Provider | Settings |
| --- | --- |
| OpenAI | `LLM_BACKEND=openai`, `OPENAI_API_KEY`, `OPENAI_MODEL=gpt-4o-mini`, `EMBEDDING_MODEL=text-embedding-3-small`, `EMBEDDING_DIMENSIONS=1536` |
| Ollama | `LLM_BACKEND=ollama`, `OLLAMA_BASE_URL=http://localhost:11434`, `OLLAMA_MODEL=llama3.2:3b`, `EMBEDDING_MODEL=nomic-embed-text`, `EMBEDDING_DIMENSIONS=768` |

OpenAI usage requires usable API credits. Vercel cannot reach a model on your laptop at `localhost`; use the local stack for Ollama. Compose sets its internal Ollama address automatically.

## Environment templates

`.env.example` is documentation, not a credential store. Python does not load it automatically. In PowerShell use `$env:NAME = "value"`; in Bash use `export NAME=value`. Set secrets privately and avoid shell-history exposure. Do not replace a working local `.env` with the template. Compose loads its own `.env` file.

## Stop local services

From the repository root:

```powershell
docker compose stop
docker compose -f appendix-a/compose.yml stop
```

These stop services while retaining data/model volumes. Start the applicable stack again when needed. Keep database ports bound to loopback for local development.
