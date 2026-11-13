# Signal Desk threat dashboard

The main page now opens the feed dashboard. The existing report processing, PDF evidence and coursework interfaces remain at `/laboratory`. Hosted authentication is unchanged.

Implemented: CIRCL/Botvrij MISP ingestion, event search and publisher filters, original-source event details, recurring observable ranking, source coverage, browser-local SHA-256/file signature inspection, message cue checking against stored indicators, optional VirusTotal hash reputation, persisted case notes/status, and JSON/observable exports. All indicator values are rendered as escaped text.

The friend's reference site is https://y-seven-nu-15.vercel.app/. This is an independent implementation of the observed workflow, not a copy of its private backend. It does not claim full parity: ThreatFox/OTX, arbitrary-file sandbox execution, archive inspection, IDS rule generation and LLM answers are not implemented. Existing PDF passage retrieval is available instead of fabricated AI answers. Optional reputation lookup requires `VIRUSTOTAL_API_KEY` in server environment; files are never submitted to it.

## Ingest

Use **Sync next feed batch** to import the bundled 15,000-observation snapshot on first use, then queue up to four changed events. The snapshot represents five source events from three publishers, not 15,000 incidents. The existing Vercel queue must be configured; failures are visible. Repeated batches skip previously imported event versions. For a larger export, from repository root:

```powershell
python tools/threat_feed.py --output data/live-threats --count 15000
python -m tools.import_threats data/live-threats
```

The importer uses the application's existing `MONGODB_URI` / `MONGODB_DB` environment configuration. Keep database credentials out of chat and source control. It performs idempotent upserts into `threat_events` and `threat_records`, and does not delete existing report or lab collections.

## Experiment 18

Copy `threats.jsonl` and `source.json` from `data/live-threats` to the revised Experiment 18 `data` directory. Use only one threats JSON/JSONL/CSV file there. The export and dashboard distinguish event count from indicator attribute count. No synthetic padding is performed.

This revision targets up to 15,000 unique indicator attributes, not 100,000 incidents. It is explicitly a reduced-workload adaptation. Source = publishing organization; target = reported observable, not victim; timestamp = attribute modification time, not attack time. Publisher overlap is not proof of a fraud ring or a false positive. Provider requests retrieve public JSON only, never visit indicator URLs or execute malware.

## Validation

Run `python -m unittest discover -s tests -v` after installing `requirements-dev.txt`. Tests use fixtures/mocked databases and do not assert live deployment success. Verify the deployed root, `/laboratory`, feed sync and counts after Vercel deploys the commit.
