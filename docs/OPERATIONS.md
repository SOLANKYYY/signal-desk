# Operations and verification

## Before a demonstration

- Confirm the latest intended commit is deployed and the production domain points to it.
- Sign in and check Threat explorer can read events from MongoDB.
- In AI Chatbot, confirm the displayed model matches the intended configuration.
- Add one public source and wait for successful import.
- Ask a specific question with both filters All; inspect the cited source.
- Ask a follow-up, reload, and confirm the completed conversation can be resumed.
- Record actual screenshots/results. A successful build, configured key, model-list response, or passing unit test is not proof of a completed AI response.

## Troubleshooting

| Symptom | Meaning / action |
| --- | --- |
| No indexed evidence | Import evidence into the current embedding space; broaden scope filters |
| Gemini model unavailable / HTTP 404 | Check the actual deployed model and endpoint against provider availability; model listing alone does not prove generation works |
| Quota / HTTP 429 | Check provider quota and reset times; do not enable billing or automatic paid fallback as an implicit repair |
| Invalid key / access denied | Check server-side key, project permissions and applicable regional restrictions; never paste keys in issues |
| Cloud backend unavailable | Inspect Vercel runtime logs for the actual exception; the generic message alone does not prove a database outage |
| Incomplete answer | Inspect the error inside the answer card; confirm provider generation and successful MongoDB save before claiming success |
| Old interface/model | Hard-refresh; verify deployment commit and that environment changes were followed by a redeploy |
| Embedding dimension mismatch | Match provider, model, dimensions, and Atlas index, then re-import sources |
| Docker engine pipe missing | Start Docker Desktop and wait for the Linux engine before running lab scripts |
| Port 27017 already used | Use the existing local MongoDB or stop the conflicting local service; do not delete volumes |

## Deployment checks

The web build copies assets from `frontend/` into generated `public/`. Edit source assets only. Vercel build logs diagnose deployment failures; runtime logs diagnose API failures. The two are separate. Retention depends on the hosting plan, so capture errors promptly and redact credentials/user content.

`MODEL_INVENTORY_CHECK=1` opts into a build-time **read-only** model-list check for saved provider keys. `scripts/provider_check.py` prints model names and access status, not keys or raw error bodies. It does not generate answers, check billable credits, or prove end-to-end operation. Leave the flag unset or `0` for normal deployments.

## Data preservation

Use separate development databases. Do not point destructive lab workloads at production Atlas. Keep result exports, screenshots and private reports outside Git. Back up important data before schema changes. Stopping Docker services preserves volumes; deleting volumes destroys their contents.

## Validation scope

Python tests use mocked databases and model responses where appropriate. The JavaScript test checks interface contracts in a simulated DOM; it is not a full browser accessibility or visual audit. Real provider, queue, database, Docker, and browser tests are separate checks.
