# Signal Desk update — 4 October 2026

The comparison below is based on the public interface observed at https://y-seven-nu-15.vercel.app/. It is not an audit of that site's private implementation. Counts and availability can change. The update keeps Signal Desk's existing Python API, MongoDB database, CTI Digest/configured RSS importers, and original annual-report repository. No other feed provider or API credential was copied or added.

| Feature | Observed on the comparison site | Signal Desk before | Signal Desk now |
|---|---|---|---|
| Search | Names, aliases, CVEs and indicators | Titles and summaries | Literal report, URL, CVE, analyst-label, linked-indicator and indexed-PDF search |
| Filters | Source, date, category and trending | Category, verdict and type | Adds publisher, date, annual-report year, sorting and reset |
| Threat profiles | Named threats with related events | Individual report review | Profiles from CVEs and analyst labels, with related reports and matching evidence |
| Annual-report evidence | Searchable passages with page citations | Metadata references | On-demand PDF indexing and paginated passage search with PDF page numbers |
| Theme | Theme toggle | Light interface | Light/dark theme saved in the browser |
| Source visibility | Feed/source totals | Publisher list and sync notices | Dedicated source health with outcomes, warnings and last check |
| External reputation lookup | VirusTotal screen visible; submission not tested | Not included | Not added; existing API setup retained |
| Review records | No editable review workflow observed on the pages inspected | Saved verdict and note | Keeps reviews and adds the latest 20 history entries plus entity labels |
| Database analysis | Metrics page visible | BSON sizes, schema alternative, exact-size workload and randomized reads | Retained; size analysis also measures evidence passages |
| Exports | No equivalent BSON workflow observed on the pages inspected | BSON dump and lab JSON | Keeps both; adds current-page report JSON and evidence-aware dump export |

The comparison site's larger event counts come from different data sources. They are not a feature that can be reproduced simply by changing a counter. Signal Desk displays only records actually present in its own database.

## What remains different

- Our bundled data is 465 annual-report metadata references plus five clearly fictional scenarios. The update does not bundle someone else's event database or pre-indexed publications.
- CVEs are detected automatically. Other names and aliases are analyst-entered labels, not automated attribution. Separate aliases are not automatically merged.
- Profiles rank mentions in local real reports, not global threat severity or worldwide activity.
- PDF indexing supports the existing repository's PDFs, up to 20 MiB, 120 pages and 500,000 extracted characters per report. It does not perform OCR. Coverage limits are displayed.
- A mention in a PDF does not prove a local compromise. Verdicts still require analyst reasoning.
- CTI Digest can still return no readable articles or an access error. Source health reports this honestly; it does not substitute fabricated events.
- Hosting and production authentication are separate future work. This package remains local.

## Validation for this update

See `TESTING.md` for the exact checks and environment limitations. Old screenshots show the previous interface; current screenshots should be captured after running this update on your machine.


## Automatic review update — 5 October 2026

Added the missing automatic review workflow: a persistent sequential PDF queue, background text-based triage, default alerts dashboard, five threat-level counters, severity filtering, supporting source excerpts/page numbers, and alert acknowledgement/reopening. Start/resume, pause and retry controls show download progress and failures. Saved analyst decisions are retained separately. Fictional and metadata-only reports do not receive invented alerts or scores.

This supersedes the earlier manual-only PDF indexing workflow; individual indexing is still available. The existing source/API setup is retained. Processing runs on the user's machine while the server is running; the package does not claim all publications have already been downloaded or reviewed.
