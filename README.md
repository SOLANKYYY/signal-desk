# Signal Desk

**A cyber threat intelligence workspace for investigating security reports, searching PDF evidence, and recording analyst decisions.**

Signal Desk brings public report metadata, extracted passages, provisional threat ratings, and review history into one browser interface. It uses Python and MongoDB, with a lightweight HTML, CSS, and JavaScript frontend.

[Features](#features) · [Quick start](#quick-start) · [Technology](#technology) · [Deployment](#deployment) · [Contributing](CONTRIBUTING.md)

## Features

- **Intelligence catalog:** search reports, summaries, CVEs, indicators, analyst labels, and indexed PDF passages. Filter by publisher, date, year, report type, category, and verdict.
- **PDF processing:** sequential download and text extraction with persistent progress, pause/resume, and explicit retry for failed publications.
- **Evidence search:** inspect matching passages, page references, related reports, and entity/CVE profiles.
- **Threat attention levels:** Critical, High, Medium, Low, and Not assessed, with supporting rule excerpts. High and critical ratings create alerts that analysts can acknowledge or reopen.
- **Analyst review:** save a category, verdict, and reasoning note, with recent review history retained separately from automatic ratings.
- **Source visibility:** inspect provenance, linked indicators, source status, and update outcomes.
- **Usable interface:** dark/light themes and JSON export of the current results page.
- **Database analysis:** inspect BSON sizes and compare a referenced model with an embedded-source alternative. Local tools also provide synthetic workloads and real WiredTiger cache measurements.

### How to interpret ratings

Ratings are transparent, rule-based indicators of the attention a report's text may deserve. They are **not confirmed incident severity, CVSS scores, machine-learning predictions, or evidence that your device is affected**. A low rating does not establish safety.

Annual-report metadata alone remains **Not assessed**. Blocked, scanned, oversized, or unreadable PDFs may also remain unassessed. Clearly marked fictional scenarios are excluded from automatic alerts. Analyst verdicts and alert acknowledgements remain separate decisions.

## Technology

| Area | Tools | Purpose |
| --- | --- | --- |
| Browser interface | HTML5, CSS3, JavaScript | Dashboard, filters, report views, and review controls |
| Application | Python 3.12+, Flask | Cloud HTTP application and processing logic |
| Local server | Python standard library | Local HTTP service and background processing |
| Database | MongoDB, PyMongo | Reports, relationships, evidence, reviews, and processing state |
| Connection support | dnspython | DNS support for MongoDB SRV connections |
| PDF extraction | pypdf | Extract searchable text and page references |
| Cloud execution | Vercel, Vercel Queues | Hosted application and queued processing |
| Hosted database | MongoDB Atlas | MongoDB hosting for cloud deployment |
| Testing | unittest, mongomock | Automated checks with isolated mock storage where appropriate |
| Optional local database | Docker Compose | Start the bundled MongoDB service |

No Node.js build is required for the frontend. Exact Python dependency versions are recorded in `requirements.txt`; development dependencies are in `requirements-dev.txt`.

## Quick start

You need **Python 3.12 or later**, Git, and a running MongoDB instance. Installing Python packages does not install MongoDB itself.

### Windows PowerShell

```powershell
git clone https://github.com/SOLANKYYY/signal-desk.git
cd signal-desk
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If MongoDB already runs locally on port 27017, start the app:

```powershell
.\.venv\Scripts\python.exe -m backend.server
```

Alternatively, if Docker Desktop is installed and running, start the bundled database first:

```powershell
docker compose up -d
.\.venv\Scripts\python.exe -m backend.server
```

Open **http://localhost:8000**. Keep the terminal running; stop the server with **Ctrl+C**. Initial startup prepares the database and seeds the report catalog. Repeated startup preserves saved reviews.

The commands call the virtual environment's Python directly, so activation is optional. If `py` is unavailable, use `python -m venv .venv`.

### macOS / Linux

```bash
git clone https://github.com/SOLANKYYY/signal-desk.git
cd signal-desk
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
# Optional, if using the bundled database and Docker is installed:
# docker compose up -d
.venv/bin/python -m backend.server
```

A reachable MongoDB instance is required before starting the app.

### First investigation

1. Open the alerts dashboard and inspect indexing progress, failed publications, and attention levels.
2. Search the intelligence feed and open a report.
3. Review its source, extracted evidence, and related entities.
4. Record an analyst verdict and explanation.
5. Acknowledge or reopen an alert as appropriate.

Automatic PDF processing can use substantial bandwidth. Pause it in the dashboard when needed. PDFs are downloaded temporarily for extraction; the application stores extracted evidence rather than a permanent PDF archive.

## Configuration

Set environment variables in your shell for local use or in the Vercel project settings for cloud use. **The application does not automatically load `.env` files.**

| Variable | Default / requirement | Purpose |
| --- | --- | --- |
| `MONGODB_URI` | Local default: `mongodb://127.0.0.1:27017` | Database connection; use your hosted URI on Vercel |
| `MONGODB_DB` | `signal_desk` | Application database |
| `PORT` | `8000` | Local HTTP port |
| `APP_USERNAME` | Cloud default: `admin` | Hosted application login name |
| `APP_PASSWORD` | Required for cloud; at least 16 characters | Hosted application password |
| `CRON_SECRET` | Required for cloud; at least 32 characters | Scheduled-request authentication |
| `AUTO_MONITOR` | `1` | Local monitoring and discovery toggle |
| `AUTO_PROCESS_REPORTS` | `1` | Initial processing preference; saved pause/resume choices take precedence |
| `SYNC_INTERVAL_SECONDS` | `300` | Local source update interval |
| `CTI_FEED_URLS` | Empty | Optional comma-separated permitted HTTPS RSS/Atom feeds |

Example local settings:

```powershell
$env:MONGODB_URI = "mongodb://127.0.0.1:27017"
$env:MONGODB_DB = "signal_desk"
.\.venv\Scripts\python.exe -m backend.server
```

Keep credentials, tokens, and private database exports out of Git. The website password and MongoDB database-user password serve different purposes.

## Deployment

The repository includes a Flask entrypoint, Vercel configuration, a queue worker, and scheduled synchronization. Follow [the Vercel deployment guide](docs/VERCEL_DEPLOYMENT.md) for account setup, secrets, Atlas permissions, networking, and verification.

| Capability | Local server | Vercel deployment |
| --- | --- | --- |
| Catalog, search, evidence, reviews, and alerts | Available | Available after configuration |
| Automatic PDF processing | Local background processor | Vercel Queues worker |
| Source synchronization | Local polling / manual action | Scheduled / manual action |
| Schema analysis | Available | Available |
| Large synthetic workload and cache measurements | Local tools | Disabled |
| Login | Local service; keep on your own machine | Single-user password gate |

Cloud operation depends on Atlas connectivity, configured secrets, and queue availability. The password gate is not a multiuser identity or role-management system. Deployment success must be checked in your own environment.

## Data sources and boundaries

- [CTI Digest](https://ctidigest.com/): discovery from readable public content and permitted feeds. Blocked or JavaScript-only pages may not be ingestible; failures remain visible.
- [Awesome Annual Security Reports](https://github.com/jacobdjwilson/awesome-annual-security-reports): catalog references to publisher reports.
- Bundled fictional scenarios use reserved `.invalid` domains and are labelled as fictional.

The initial catalog contains metadata references, not a pre-reviewed collection of PDFs. Counts change as sources are synchronized. Original reports remain the work of their publishers; links and extracted evidence do not imply endorsement. See [data provenance](data/PROVENANCE.md).

The processor retrieves report PDFs; it does not download malware or contact addresses merely because they appear as indicators in a report.

## Project structure

| Path | Responsibility |
| --- | --- |
| `frontend/` | Browser layout, styling, and interaction |
| `backend/` | HTTP routes, ingestion, evidence extraction, alerts, database operations, and analysis tools |
| `app.py` | Flask deployment entrypoint |
| `worker.py` | Cloud queue subscriber |
| `data/` | Seed metadata, provenance, and bundled BSON data |
| `docs/` | Setup, operation, technical details, and validation notes |
| `mongodb/` | Optional MongoDB helper scripts |
| `scripts/` | Build helpers |
| `tests/` | Automated Python checks |
| `results/` | Locally generated analysis output |
| `vercel.json`, `pyproject.toml` | Deployment and Python project configuration |

## Development and testing

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The automated suite includes controlled downloads and mock database/queue operations. Passing it does not establish real Atlas connectivity, Vercel queue delivery, or performance. Validate those separately in the deployed environment.

See [Contributing](CONTRIBUTING.md) and [the GitHub workflow](docs/GITHUB_WORKFLOW.md) for changes, commits, and pull requests.

## Documentation

- [User guide](docs/USER_GUIDE.md)
- [Technical guide](docs/TECHNICAL_GUIDE.md)
- [Vercel deployment](docs/VERCEL_DEPLOYMENT.md)
- [Validation history](docs/TESTING.md)
- [GitHub setup and update commands](docs/GITHUB_WORKFLOW.md)
- [Security guidance](SECURITY.md)

## Maintainer

Maintained by [SOLANKYYY](https://github.com/SOLANKYYY).
