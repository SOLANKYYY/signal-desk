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
