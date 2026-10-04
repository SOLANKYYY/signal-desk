# Demo and submission checklist

Use this guide to demonstrate the platform and prepare the project files.

## Five-minute demonstration

1. Launch the app and show the catalog count and publisher directory.
2. Search `ransomware`, filter to training/articles, open the fictional report and explain that keywords identify the topic only.
3. Save a justified verdict. Refresh to show persistence. Explain the difference between a trusted publisher and the malicious activity it describes.
4. Open Schema analysis, run BSON measurement, build the alternative schema and explain read simplicity versus duplicate publisher updates.
5. Open Working-set analysis. Generate the workload ahead of the demo if necessary. Show the real 100,000 count and 2,048-byte BSON sizes.
6. Show cache capacity, start three randomized passes, and explain the page-counter estimate and 10-second monitor.
7. Check new reports and show either inserted/deduplicated results or the explicit source-access warning. Do not claim a blocked source succeeded.

## Before uploading

- Fill your name, roll number and course details in `TECHNICAL_GUIDE.md`.
- Run every lab locally, then fill its observation table with your measured results.
- Save screenshots of report review, schema-size output, and cache/read results in `docs/your-screenshots/`.
- Run `python -m backend.dump export` with your virtual-environment interpreter if you want your reviewed report state in the dump.
- Include `results/` with your measurements and `data/dump/` with the BSON files.
- Exclude `.venv/`, `__pycache__/`, credentials, MongoDB storage files, and downloaded report PDFs from your final ZIP.
- `validation-results/` is evidence of preparation testing, not a substitute for your own observations.

## Viva questions you should be ready to answer

**Why reference sources?** Many reports share one publisher; edit the source once instead of updating duplicated copies.

**Why embed assessment?** It is small, bounded, owned by a report and read with that report.

**What is the BSON limit?** 16,777,216 bytes per document. The 80% warning threshold is chosen by the project.

**Why not insert 100,000 real reports?** The supplied dataset is a finite catalog. Workload expansion is explicit and synthetic, solely to meet the cache experiment.

**What is a working set?** The data and indexes actively accessed by the workload, not necessarily all stored data.

**Does occupancy mean the percentage of our data cached?** No. It is instance-wide bytes in use divided by configured cache bytes.

**Why use deltas?** The counters are cumulative; differences isolate one observation interval more usefully than lifetime totals.

**Why might the first read pass already be fast?** Insertion can warm the WiredTiger cache; the OS cache may also help.

**Why is a source not an actual threat?** A publisher may report malicious activity without being malicious itself. Evidence-based review applies to reported activity/observations.


## New investigation workflow

1. Use the publisher and report-year filters to narrow annual publications. Use publication dates for dated news items; undated entries are excluded by a date filter.
2. Open **Report evidence**, choose a publication, and select **Index selected PDF**. Wait for the job outcome. The PDF must be hosted in our existing annual-report repository.
3. Search a phrase, CVE or threat name. Each result shows its PDF page and a link to the original. Read the source context before recording a verdict.
4. Open **Threat & CVE profiles** for CVEs detected in indexed text. While reviewing a report, add supported names/aliases as comma-separated labels. Each label gets a profile showing related local reports. Fictional scenarios are excluded from these counts.
5. Save a review and reopen it to inspect **Recent review history**. Up to 20 entries are kept per report.
6. Open **Sources & indicators** for source health. If CTI Digest is unavailable, its warning remains visible; the annual catalog still works.
7. Switch themes in the header. **Export this page** downloads the currently displayed reports and their metadata as JSON, not the entire filtered dataset.

The new evidence index starts empty. A large catalog count does not mean every PDF has been downloaded or verified. A PDF with no selectable text needs OCR outside this app. Partial extraction is labelled with its coverage.


## Automatic processing and alert review

1. Start the server and open **Alerts & threat levels**. New installations begin processing automatically. If a previous session was paused, click **Start / resume all**.
2. Watch the indexed/failed/remaining counts and current title. Downloads and text extraction run sequentially. You can browse the feed while processing continues.
3. Open **Download failures** for up to ten recent listed failures and click **Retry failed downloads** after resolving access/network problems. Normal restarts do not repeatedly retry failed documents.
4. Read each alert's level, reason, source excerpt, PDF page and publication year. Open **Review evidence** for the full assessment and source link. An old report may describe historical exploitation.
5. Use **Acknowledge alert** to remove it from the default open queue. Enable **Include acknowledged alerts** to find it and reopen it. This does not change the saved manual verdict.
6. In **Intelligence feed**, filter by threat level to inspect medium/low/unassessed reports as well as alerts.
7. Pause automatic processing and wait for the current report to finish before taking cache measurements. The queue resumes from MongoDB state when you start it again.

Ratings: critical = active-exploitation wording; high = ransomware attack/campaign, credential theft, destructive malware or exfiltration wording; medium = general threat/vulnerability discussion; low = no higher-priority rule matched; not assessed = insufficient source text or a fictional example. Common negation/fictional cues are excluded, but these are conservative text rules with possible false positives and false negatives—not automated incident verification.
