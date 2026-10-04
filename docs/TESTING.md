# Validation performed during preparation

Date: 30 September 2026. These are real preparation-environment observations, not your submission measurements. Run the project and fill the observation table yourself.

Environment: Python 3.12, PyMongo 4.18.2, MongoDB Community 8.0.12, WiredTiger cache configured to 0.3 GiB (server reported 321,912,832 bytes). The database path was memory-backed; these timings do not measure a physical disk. Unrelated process-memory sections were excluded from serverStatus; actual WiredTiger counters were read.

## Checks completed

- Nine unit tests passed: keyword classification, non-threat content, interval formula, missing/reset/idle counters, server restart detection, safe links, annual-report parsing/deduplication, RSS parsing, and exact BSON sizes across ID ranges.
- Seed inserted 470 reports (465 annual references + 5 fictional scenarios), 341 publisher-origin records, 5 indicators, and 5 observations. Repeated seeding inserted zero reports.
- Real MongoDB text search, report-type filtering, detail lookup, analyst review, review persistence across seeding, and BSON dump restoration passed.
- Embedded-source alternative generated 470 records and saved execution plans.
- Working-set generation produced 100,000 records. MongoDB measured minimum, average and maximum BSON size as exactly 2,048 bytes.
- Three randomized passes each read all 100,000 full documents.
- Desktop and mobile browser flows rendered; search, review submission, schema results and cache-capacity inspection passed with zero JavaScript page errors.
- HTTP background-job execution completed successfully; the independent monitor produced real interval counters at a 10-second interval.
- A live annual-report check parsed 465 entries and inserted zero already-known URLs. CTI Digest ingestion reported unavailable (no readable public article/feed entries); no live articles were invented.

## Measured randomized reads

| Pass | Documents read | Seconds | Estimated interval hit ratio |
|---|---:|---:|---:|
| 1 | 100,000 | 0.853 | 99.9866% |
| 2 | 100,000 | 0.811 | 100.0000% |
| 3 | 100,000 | 0.840 | 100.0000% |

These passes followed insertion and were warm-cache observations. The screenshots and separate capacity/monitor samples were captured after subsequent server restarts and schema reads; do not combine their values into one uninterrupted benchmark. Reports were briefly edited during UI testing; the original seed dump was then restored. The size-output file reflects the test state when measured.

The package's `results/` directory is deliberately empty. Your app reads only that directory for displayed lab results; it does not substitute these preparation measurements.

The interface and sample wording were subsequently renamed. These measurements predate that text-only change; rerun size analysis for current document byte counts.


## Investigation update validation — 4 October 2026

- All 17 automated tests passed on Python 3.12: the original nine checks, three entity/PDF safety/extraction checks, and five HTTP API integration checks.
- HTTP tests used a disposable `mongomock` database. They verified linked-indicator search, publisher/year filters, publication-date boundaries, PDF-evidence matching, label validation, entity profiles, review history, and review preservation across seeding. They do not establish real MongoDB performance.
- A live download from the existing catalog was successfully parsed: Beazley Security's 2026 Q1 report yielded 70 passages across all 25 PDF pages. A CVE was extracted, and a second indexing call reused the existing result. Storage for this check was disposable and mocked; extracted publisher text is not bundled.
- JavaScript syntax and Python compilation checks passed.
- A fresh MongoDB 8.0.12 process could not start in the current execution environment (`open: Operation not permitted`). The real-MongoDB measurements above remain historical checks of the previous version; this update was not re-benchmarked on a running real MongoDB instance.
- The cloud test browser rejected the local preview URL (`ERR_BLOCKED_BY_CLIENT`), so no updated visual/browser-flow validation is claimed. Existing screenshots are historical. Validate the new screens locally before publishing.
- The existing API and provider configuration was retained. No VirusTotal, alternate MISP feed, or new external API key was introduced.

To run the full Python suite, install development dependencies and run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

With only `requirements.txt`, the 12 core/PDF tests run and the five mock HTTP tests are skipped. The mock is used only in tests; the application requires a real MongoDB connection and never falls back to mock data.


## Automatic review validation — 5 October 2026

- All **25 Python tests passed**. Added checks cover severity ordering, supporting PDF pages, insufficient metadata, fictional/negated/hypothetical claims, summary-text requirements, failed-download retry, pause/resume persistence, interrupted-item recovery, reuse of completed items, preservation of saved analyst reviews, alert acknowledgement/reopening, and filtering unassessed records before triage has run.
- Queue and HTTP tests use disposable mock storage and controlled downloads. They do not claim real MongoDB performance or validate all upstream publications.
- An in-memory DOM check using jsdom passed for dashboard initialization, all five level cards, report-level display, source-excerpt/page rendering, HTML escaping, report detail, pause controls and acknowledgement. This is a DOM behavior test, not a visual browser screenshot test.
- Python compilation, JavaScript syntax and HTML element-reference checks passed. Existing real-MongoDB/browser environment limitations above remain; no new visual or live-MongoDB claim is made.

The application itself still requires real MongoDB. It never substitutes mock storage or test alerts. Automatic processing begins with the user's actual catalog when the server starts. The package contains no precomputed claims that all catalog PDFs were reviewed.

- Live-source end-to-end check: the automatic processor downloaded the existing catalog's Beazley Security Q1 2026 PDF, extracted all 25 pages into 70 passages, and generated a provisional critical report-attention alert with six supporting rule excerpts. The queue reached zero remaining items in this one-report test. The PDF source was live; storage was disposable and mocked. This is not a claim that a current attack occurred or that the full catalog was processed.
