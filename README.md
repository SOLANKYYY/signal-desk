# Signal Desk

A Cyber Threat Intelligence workspace for report investigation, PDF evidence, analyst review, schema analysis, and cache measurement. It includes a browser frontend, Python API, MongoDB, real BSON dump, repeatable lab commands, and written answers.

**Deploy to Vercel:** follow `docs/VERCEL_DEPLOYMENT.md`. This package includes the Flask entrypoint, durable PDF queue, password gate, and hosted MongoDB support. Cloud setup and production verification are still required. Cache monitoring and large database workloads remain local.

**Start here:** run the application below, then follow `docs/USER_GUIDE.md`. The full academic explanation is in `docs/TECHNICAL_GUIDE.md`.

## What is included

- Automatic PDF processing queue with persistent progress, pause/resume and failed-download retry.
- Alerts dashboard with critical/high/medium/low/not-assessed counts and source excerpts.
- Search titles, summaries, URLs, CVEs, analyst labels, linked indicators, and indexed PDF passages.
- Publisher, publication-date, annual-report year, category, type, verdict and sorting controls.
- Threat/CVE profiles with related reports and page-numbered PDF evidence.
- Automatic sequential PDF indexing from the existing annual-report repository; optional single-report indexing remains available.
- Dark/light themes, source health, recent review history and current-page JSON export.
- Report provenance, linked indicators and evidence-based manual classification.
- 465 real annual-report *metadata references* from the original repository.
- Five clearly marked fictional CTI scenarios using reserved `.invalid` domains.
- Referenced publisher/indicator relationships and bounded embedded report metadata.
- `$bsonSize` analysis, 16 MiB limit checks, and a runnable embedded-source alternative.
- Exactly 100,000 synthetic workload documents, each exactly 2,048 BSON bytes.
- Real `serverStatus` counters, 10-second cache sampling and 3 randomized full read passes.
- Independent polling for new annual-report and publicly available CTI/feed entries.
- A restorable BSON dump plus checksums, unit tests and validation notes.

The interface's cache values come from your MongoDB instance. No cache telemetry or threat-confirmation score is fabricated. The Vercel version requires a website password and hosted MongoDB; the local version should stay on your own machine.

## Requirements

- Python **3.12 or later** with pip.
- **MongoDB Community 7/8** running locally, or Docker Desktop if you choose the bundled container.
- Internet for the initial Python/MongoDB downloads and optional live metadata updates. The bundled catalog works offline after setup.
- About 1 GB of free storage and enough RAM for Python plus MongoDB. Generation may take tens of seconds or longer depending on the machine.

No Node.js, frontend build command, new API key or paid service is required. This update keeps the existing API/data-source setup; it does not add the comparison website’s feed providers or VirusTotal.

## Run on Windows (PowerShell)

Unzip the project. Open PowerShell **inside the `signal-desk` folder**, where `requirements.txt` lives.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Only if MongoDB is NOT already running and Docker is installed:
# docker compose up -d
.\.venv\Scripts\python.exe -m backend.server
```

If `py` is unavailable, use `python -m venv .venv`. No PowerShell activation-policy changes are needed because the commands call the virtual-environment interpreter directly.

Open **http://localhost:8000**. The first start creates indexes and seeds the catalog; repeated starts preserve existing analyst reviews. Keep the terminal open. Stop with Ctrl+C.

If you already have MongoDB running on port 27017, skip `docker compose up -d`. Do not start two MongoDB servers on the same port.

## Run on macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
docker compose up -d
.venv/bin/python -m backend.server
```

Open http://localhost:8000.

## Use the website

1. The **Alerts & threat levels** dashboard opens first. Automatic PDF processing starts while the server is running. Its first pass downloads catalog PDFs sequentially and can take a long time/use substantial bandwidth. Inspect indexed, failed and remaining counts; Pause/Resume controls persist across restarts. Open **Intelligence feed**. Search for `ransomware`; filter report type to training/articles. Open a fictional report, inspect its source and indicators, and save an assessment with a reasoning note. The rule only assigns a topic; you make the evidence-based verdict.
2. Open **Sources & indicators** to inspect referenced identities.
3. Open **Schema laboratory** → **Run $bsonSize analysis**.
4. Click **Build embedded source alternative**, then rerun the size analysis to include the alternative collection. See the generated execution plans in `results/schema_redesign.json`.
5. Pause automatic report processing in **Alerts & threat levels**, wait for the current report to finish, then open **Working set** → **Generate 100,000 lab documents**. Wait for completion. Only the disposable `working_set` collection is replaced.
6. Click **Inspect cache capacity**, then **Run 3 randomized full passes**. Cache sampling continues every 10 seconds. A pass may complete between monitor samples; the CLI also captures counters at each pass boundary.
7. Return to Schema laboratory and rerun the size analysis to verify all 100,000 documents have an average/minimum/maximum BSON size of 2,048 bytes.
8. Download lab results JSON, take screenshots, and complete your measured-observation table in `docs/TECHNICAL_GUIDE.md`.

Keep the backend running while a job executes. Jobs are serialized within the website. Do not run CLI regeneration at the same time as a web experiment. Refreshing the browser does not cancel a job, but stopping the server does.

## Run the labs through commands

These examples use Windows. On macOS/Linux replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`.

```powershell
# Optional: restore the included BSON application dump into the configured DB.
# Matching IDs are replaced, so do this BEFORE making your own assessments.
.\.venv\Scripts\python.exe -m backend.dump restore

# Idempotent seed, schema measurements, embedded alternative.
.\.venv\Scripts\python.exe -m backend.labs seed
.\.venv\Scripts\python.exe -m backend.labs sizes
.\.venv\Scripts\python.exe -m backend.labs redesign

# Generate and measure a real MongoDB workload.
.\.venv\Scripts\python.exe -m backend.labs generate
.\.venv\Scripts\python.exe -m backend.labs sizes
.\.venv\Scripts\python.exe -m backend.labs capacity
.\.venv\Scripts\python.exe -m backend.labs reads --passes 3

# Optional separate terminal: real telemetry and new-report checks.
# Do not run this if the web server's built-in monitor is already enabled.
.\.venv\Scripts\python.exe -m backend.labs monitor

# One-off check for new public reports.
.\.venv\Scripts\python.exe -m backend.labs sync

# After your own work, refresh the application BSON dump for submission.
.\.venv\Scripts\python.exe -m backend.dump export

# Unit tests (no running MongoDB server needed).
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The bundled seed dump contains `sources`, `reports`, `indicators`, and `observations`. New exports also include `evidence_passages` and `import_state`; restore accepts the older four-collection format. PDF text is indexed on your machine, not preloaded or redistributed in this ZIP. The 195 MiB workload is generated on demand and excluded from the ZIP to keep it small. `backend.dump restore` retains BSON types and verifies counts/checksums. You may also use MongoDB Database Tools `mongorestore --db signal_desk data/dump` for the BSON collection files; the supplied Python restore command does not require Database Tools and recreates indexes.

## Configuration

Environment variables are optional; the defaults work with the bundled Docker configuration.

| Variable | Default | Meaning |
|---|---|---|
| `MONGODB_URI` | `mongodb://127.0.0.1:27017` | MongoDB connection URI |
| `MONGODB_DB` | `signal_desk` | Dedicated coursework database |
| `PORT` | `8000` | Local HTTP port |
| `AUTO_MONITOR` | `1` | Set `0` to disable sampling/discovery; pause automatic PDF processing separately before isolated benchmarks |
| `AUTO_PROCESS_REPORTS` | `1` | Initial automatic PDF-processing preference; later Start/Pause choices persist in MongoDB and take precedence |
| `SYNC_INTERVAL_SECONDS` | `300` | New-report polling delay after each completed attempt; cache sampling remains 10 seconds |
| `CTI_FEED_URLS` | empty | Comma-separated permitted HTTPS RSS/Atom feed URLs |

Example in PowerShell:

```powershell
$env:SYNC_INTERVAL_SECONDS="300"
$env:MONGODB_URI="mongodb://127.0.0.1:27017"
.\.venv\Scripts\python.exe -m backend.server
```

The app does not load `.env` files automatically. Set variables in the shell. Keep credentials out of submitted code and screenshots.

## Source availability and interpretation

CTI Digest's public page exposes the concept of news, sources and an IOC registry. Automated retrieval returned HTTP 403 during preparation. The importer handles readable article HTML and discovered RSS/Atom feeds, or configured permitted feeds. It cannot promise compatibility with a blocked or JavaScript-only source. Source failures remain visible; other imports and the bundled lab remain usable. The annual-report parser handles the repository's current report-bullet format and fails clearly when no entries are found.

The GitHub dataset is a report catalog, not a labeled incident dataset or 100,000-row MongoDB dump. The seed includes metadata only. The 100,000 generated records are explicitly synthetic. Classification uses transparent keyword topic rules plus human review; it does not claim ML accuracy or determine maliciousness from a publisher's name.

## Project layout

```text
signal-desk/
  frontend/          HTML, CSS and JavaScript browser interface
  backend/           API, schema, ingestion, lab commands, monitor, dump tools
  data/              Report metadata snapshot, provenance notes, BSON dump
  docs/              Lab answers, submission guide and interface screenshots
  mongodb/           Optional mongosh indexing and BSON verification scripts
  tests/             Parser, classifier, BSON size and cache-delta tests
  results/           Your newly generated measurements (initially empty)
  validation-results/  Measurements from the preparation test environment
  requirements.txt
  docker-compose.yml
  README.md
```

## API overview

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Check MongoDB connection |
| `GET /api/summary` | Counts and classification totals |
| `GET /api/reports?q=...&category=...&verdict=...&kind=...&page=1` | Search/filter/paginate |
| `GET /api/reports/{id}` | Detail, publisher and linked indicators |
| `POST /api/review/{id}` | Save category, verdict and evidence note |
| `GET /api/sources`, `GET /api/indicators` | Reference directories |
| `GET /api/metrics` | Latest real cache sample and recent history |
| `GET /api/capacity` | Cache capacity and collection-size estimate |
| `POST /api/jobs/{sizes,redesign,generate,reads,sync}` | Run a background task |
| `GET /api/jobs`, `GET /api/results` | Job states and generated lab outputs |
| `GET /api/entities`, `GET /api/entity?name=...` | Local entity counts and related reports |
| `GET /api/catalog`, `GET /api/evidence?q=...&page=1` | PDF catalog and passage search |
| `POST /api/jobs/index-pdf` with `{ "reportId": "..." }` | Index a catalog PDF in the background |
| `GET /api/source-status` | Source-check outcomes and cadence |
| `GET /api/processing`, `POST /api/processing` | Queue status; body action `start`, `pause`, or `retry` |
| `GET /api/alerts?level=critical&ack=1&page=1` | Provisional report alerts and severity counts |
| `POST /api/alerts/{id}` | Set alert status to `acknowledged` or `open` |

## Troubleshooting

- **Connection refused / server selection timeout:** start MongoDB, check port 27017, and wait for `docker compose ps` to show a healthy service. Python dependencies do not install the database server.
- **Docker unavailable:** install/start MongoDB Community locally, or install/start Docker Desktop. The web server needs a real MongoDB instance.
- **`serverStatus` unauthorized or WiredTiger metrics unavailable:** use the local Docker instance for this lab. A remote authenticated setup needs read/write access to this lab DB plus monitoring privileges (for example the `clusterMonitor` role on `admin`). Some managed tiers restrict these counters.
- **Hit ratio N/A:** wait for an interval with reads. First samples, idle periods, unavailable/reset/incomparable counters intentionally have no ratio.
- **Hit ratio already high on pass 1:** generation warms the cache; this is expected and not evidence of a broken experiment.
- **CTI source blocked:** review the sync warning. Use the bundled training data or configure an authorized public RSS feed. No login or bypass is attempted.
- **Incomplete generation after interruption:** run generation again; it rebuilds only `working_set`.
- **Port 8000 occupied:** set `PORT` to 8001 and open that port.

To stop the Docker service without deleting its data, use `docker compose stop`. Do not delete the volume unless you intend to remove your lab data.

## Upgrade from your previous download

1. Stop the running Python server with Ctrl+C.
2. Extract the new ZIP and use its `signal-desk` folder. Keep the same MongoDB connection/database settings. Your database stores your existing assessments independently of the project folder.
3. Run `py -m venv .venv` if this is a fresh folder, then `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` to install the added PDF reader.
4. Start `.\.venv\Scripts\python.exe -m backend.server` and open http://localhost:8000. Keep the terminal running. Refresh the browser to load the new interface.
5. Do not restore the sample dump over your saved work. Startup applies additive indexes/entity fields and preserves saved verdicts and notes. Keep copies of any `results/` files you generated in the previous folder.

Your earlier log showed a successful database connection, so you can skip Docker while that MongoDB service is running.

See `docs/UPDATE_NOTES.md` for the feature comparison, new workflows and limitations. The local version has not been published.


## Automatic ratings and alerts

The dashboard shows **Critical**, **High**, **Medium**, **Low**, or **Not assessed**. Ratings describe the attention needed for the text in a report. They are provisional rules, not verified incident severity, a CVSS score, or proof that your own system is affected. High and critical reports create alerts. Each alert gives its rule, source excerpt, publication year when available, and PDF page. You can acknowledge/reopen alerts independently of saved analyst verdicts.

Annual-report titles and metadata alone receive **Not assessed**. The worker attempts each catalog PDF once and persists failures for explicit retry. Successful extraction is cached as searchable passages; already-indexed reports are reused on restart. PDFs themselves are temporary, and no threat files or indicator addresses are downloaded/contacted. Download, extraction and page/text limits from the previous version remain in force. Fictional scenarios never create automatic alerts. Original APIs and data sources are unchanged.

Keep the terminal running for processing to continue. The ZIP contains the processor, not 465 pre-downloaded/verified PDFs. A blocked, oversized, scanned or unreadable publication may remain unassessed. Use the failure panel to inspect the reason. Low priority means no higher-priority rule matched; it does not establish safety.
