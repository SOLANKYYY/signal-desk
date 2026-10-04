# Signal Desk — Technical guide

Student name: ____________________  Roll number: ____________________
Course / division: ____________________  Date: ____________________

## Aim
Build a cyber threat intelligence platform and use its MongoDB data to investigate embedding, referencing, BSON document limits and WiredTiger working-set behavior.

## Data and scope
The application has a Python backend, a browser frontend, and MongoDB. It models the news/source/IOC structure visible on CTI Digest. The bundled catalog has 465 annual-report references extracted from the specified GitHub repository, plus five original fictional training reports and five fictional domain indicators. It is a production-style educational schema, not an exported private production database. CTI Digest rejected automated requests during preparation; the application reports that condition rather than inventing live articles.

`data/dump/` contains a real, restorable BSON dump of the four application collections. `backend.dump` exports and restores concatenated BSON documents while retaining types and checking SHA-256 hashes. No downloaded report PDF is executed or redistributed.

## Schema analysis — Analyze a production schema

### Relationships and design decisions

| Relationship | Design used | Why | Embedded alternative and cost |
|---|---|---|---|
| Report → publisher/source | `reports.sourceId` references `sources._id` | Many reports share a publisher; changing its name/URL should require one write | Copy publisher name/URL into every report; detail reads need no lookup, but updates fan out and copies become stale |
| Observation → report | `observations.reportId` references `reports._id` | A report can have many indicator observations; do not grow an unlimited report array | Embed all observations inside a report; convenient per-report read, but a large indicator set can approach 16 MiB |
| Observation → indicator | `observations.indicatorId` references `indicators._id` | An indicator may appear in many reports, so store its identity once | Embed an indicator object in each observation; repeated values and independent corrections require multiple writes |
| Report → assessment | One embedded `assessment` object | Current category, verdict, evidence note and reviewer timestamp are bounded and read with the report | A separate assessment collection would require a lookup for a small one-to-one object |
| Report → provenance | One embedded `provenance` object | Origin and synthetic flag belong to this report and are always useful when reviewing it | Referencing adds unnecessary indirection for this small owned object |
| Assessment → matched terms | Bounded array (maximum 12 terms) | Small explanatory result of classification | A collection of individual keywords would add avoidable query complexity |

`assessment` stores the latest review only. If full review history is required, use a separate history collection rather than an unlimited embedded audit array. Current writes cap titles, summaries, evidence notes and matched terms. BSON measurements verify the generated data; they do not prove that arbitrary future imports are safe.

### Example referenced document

```javascript
{
  _id: "report-id",
  sourceId: "publisher-id",
  title: "Example report",
  assessment: {
    category: "phishing", verdict: "needs-review",
    matchedTerms: ["phishing"], method: "keyword-triage-v1",
    note: "Review the evidence before confirming a threat."
  },
  provenance: { origin: "https://ctidigest.com/", synthetic: true }
}
```

### Calculate BSON size

Run `python -m backend.labs sizes`. The script uses the actual `$bsonSize` expression:

```javascript
db.reports.aggregate([
  {$project: {bytes: {$bsonSize: "$$ROOT"}}},
  {$group: {
    _id: null,
    count: {$sum: 1},
    averageBytes: {$avg: "$bytes"},
    maximumBytes: {$max: "$bytes"}
  }}
])
```

The BSON limit is **16 MiB = 16,777,216 bytes** per document. The project explicitly defines “approaching the limit” as at least 80% of that limit; this is a project threshold, not a MongoDB rule. The generated `results/schema_sizes.json` includes each collection's average, maximum, largest-document percentage, and count at or above the threshold. A collection with no documents is recorded with count zero, not treated as evidence of a safe design.

### Schema design — Embedded redesign

Run `python -m backend.labs redesign`. It uses `$lookup` to obtain the publisher and `$out` to create the disposable alternative `reports_embedded`; canonical reports are preserved. In the alternative, a full `source` object replaces `sourceId` and includes a snapshot timestamp.

Faster/simpler query: retrieve a report with its publisher details using one collection lookup instead of joining `sources`. Filtering/report rendering that needs the source name can avoid a join too (with suitable indexes for the filter).

Harder operation: correct a publisher URL or source name, because every embedded copy must be updated. Counts grouped by canonical publisher identity need careful deduplication; old source details may persist in snapshots. The extra source bytes increase the data footprint and reduce the number of reports that can reside in a fixed cache. For this small data size, measured latency may be indistinguishable: fewer joins is a structural advantage, not a guaranteed timing improvement.

`results/schema_redesign.json` contains execution-statistics explains for equivalent single-report retrievals. It is a comparison of access plans, not a rigorous latency benchmark. Rebuild the snapshot after source or report changes; subsequent reviews intentionally update only canonical reports.

### Deciding whether something is an actual threat

A publisher/source is not itself a threat merely because it publishes security articles. Here, “actual threat” applies to the activity described in the report. Keyword rules propose a topic; the initial verdict is always `needs-review`. The student reviews provenance, linked evidence, and context, then records one of:

- `confirmed-threat`: the reported malicious activity is supported by evidence; write the evidence in the note.
- `benign`: the observed activity has a supported benign explanation; record it.
- `needs-review`: insufficient information or unresolved ambiguity.

A general annual-report entry alone should ordinarily remain `needs-review`. The platform does not require an ML classifier; no untrained AI model or accuracy score is claimed. Fictional examples can be reviewed as demonstrations, but their verdicts are not claims about real-world threats.

## Working-set analysis — Working-set analysis

### Generate the workload

Run `python -m backend.labs generate`. It creates exactly **100,000 documents × 2,048 BSON bytes = 204,800,000 bytes = 195.3125 MiB** of logical document data, before indexes, storage-engine overhead, or compression. Each document references an annual-report template and contains deterministic, varied ASCII padding. These are synthetic repetitions for performance testing, not 100,000 unique publications. Insertion uses batches of 1,000.

The `_id` index is retained. Reads request complete documents including padding, so the test cannot be satisfied from a covered index alone.

### Check cache size and occupancy

Run `python -m backend.labs capacity` or inspect the Working set page. The backend executes `serverStatus` against the connected server and reads:

| Counter | Meaning |
|---|---|
| `maximum bytes configured` | Configured maximum WiredTiger cache bytes |
| `bytes currently in the cache` | Current bytes held in the instance-wide cache |
| `tracked dirty bytes in the cache` | Modified cache bytes |
| `pages requested from the cache` | Cumulative page requests |
| `pages read into cache` | Cumulative page reads into the cache |
| `eviction pages evicted by application threads` | Application-thread eviction counter, when available |

`cache occupancy % = 100 × bytes currently in cache / maximum bytes configured`.

**This is not the percentage of the working_set collection resident in cache.** WiredTiger allocates cache across the mongod instance. Other collections, indexes, internal structures and writes consume it too. `collStats.size` plus on-disk index size is only a rough planning estimate, not an exact resident-memory requirement. WiredTiger's in-cache data representation differs from compressed storage; operating-system file cache adds another layer.

The Docker configuration uses a 0.3 GiB cache (roughly 307.2 MiB). The 195.3125 MiB logical workload might fit, but indexes, metadata, other collections and access patterns affect actual behavior. Use measurements to draw the conclusion.

### Random reads and interval estimate

Run `python -m backend.labs reads --passes 3`. Each pass shuffles all 100,000 IDs and retrieves them in indexed `$in` batches of 200. Every document is visited once per pass; grouping in batches means this is not 100,000 separate network round trips. The script records elapsed time, documents/second, median/p95 batch latency and interval page-counter differences.

For two valid consecutive samples:

```text
requests_delta = requests_now - requests_previous
reads_delta    = pages_read_now - pages_read_previous
estimated_hit_ratio = 100 × (1 - reads_delta / requests_delta)
```

The ratio is a **page-counter estimate**, not MongoDB's exact application/query hit-rate metric. Record `N/A` when there is no prior sample, zero page requests, a counter reset/server restart, unavailable counters, or incomparable deltas. Do not force these conditions to zero or 100%. Page prefetch, writes, and unrelated traffic can affect counters.

The teacher's sample script uses evictions relative to reads as an approximation. This solution deliberately does not equate eviction count with cache misses; it reports page-request/read deltas and preserves raw counters. Both the distinction and formula should be explained during the viva.

### Cache monitoring — Monitor new reports and cache

`python -m backend.labs monitor` runs two independent loops:

1. Sample `serverStatus` every 10 seconds and append data to `results/cache_monitor.jsonl` and the TTL-limited `cache_samples` collection.
2. Check the public annual-report README and CTI Digest/discovered or configured RSS feeds. The default discovery interval is 300 seconds after each completed attempt; HTTP timeouts can make discovery slower. Network fetches run separately and do not block the sampler. Use `SYNC_INTERVAL_SECONDS` to configure discovery without changing the 10-second cache sampler.

Imports deduplicate by a unique canonical URL and use insert-only upserts so existing analyst verdicts are not overwritten. Annual-report discovery uses HTTP ETags where available. A blocked site, changed markup, unsupported JavaScript-rendered feed, or fetch failure produces a warning; no fictional “new report” is silently inserted. `CTI_FEED_URLS` can contain administrator-selected permitted HTTPS RSS/Atom feeds. Already-known report metadata is not refreshed: this platform detects new URLs.

### Interpreting observations

- Higher later-pass estimates plus fewer page reads and similar/higher throughput can be consistent with warming, if the workload fits.
- Persistent reads/evictions may suggest pressure, but correlate counters with workload and other activity.
- High initial estimates are possible because insertion already warmed the cache.
- Do not claim a cold-cache measurement immediately after generation. For a controlled comparison, stop the app/monitor, restart only the dedicated test mongod, then run reads. This clears WiredTiger memory but may leave the OS filesystem cache warm.
- Run the monitor alongside reads when observing the 10-second history, and document concurrent discovery traffic. For less-confounded pass comparisons run the CLI with the web server/monitor stopped.
- The scratch validation environment used a memory-backed database path; its elapsed times do not represent physical-disk performance. Repeat on your own machine and report its configuration.

### Fill from your own run

| Measurement | Your observation |
|---|---|
| MongoDB version / RAM / cache capacity | __________ |
| Workload document count / average BSON bytes | __________ |
| Maximum report BSON bytes / near-limit count | __________ |
| Pass 1 seconds / estimated hit ratio | __________ |
| Pass 2 seconds / estimated hit ratio | __________ |
| Pass 3 seconds / estimated hit ratio | __________ |
| Cache occupancy before / after | __________ |
| Concurrent processes, collection sizes, indexes | __________ |
| Working-set conclusion and supporting numbers | __________ |

## Conclusion
The schema uses bounded embedding for owned report metadata and references for shared identities and potentially growing relationships. The embedded source alternative trades fewer read-time joins for duplicated data and more expensive corrections. `$bsonSize` measures the actual risk relative to the document limit. The cache experiment measures workload behavior using real WiredTiger counters while separating logical dataset size, compressed storage size, cache occupancy and approximate page hit ratio.

## References

- Assignment CTI source: https://ctidigest.com/
- Assignment report dataset: https://github.com/jacobdjwilson/awesome-annual-security-reports/
- BSON size expression: https://www.mongodb.com/docs/manual/reference/operator/aggregation/bsonSize/
- BSON document limit: https://www.mongodb.com/docs/manual/reference/limits/
- WiredTiger cache behavior: https://www.mongodb.com/docs/manual/core/wiredtiger/
- Server status counters: https://www.mongodb.com/docs/manual/reference/command/serverStatus/

Original implementation for this project; teacher scripts were read as references, not copied into the submission.


## Investigation update

Reports now hold bounded `entities` (up to 40), analyst-supplied entity labels (up to 20), PDF coverage metadata, and the most recent 20 review-history entries. CVEs are detected in titles, summaries and extracted PDF text. Names and aliases entered by an analyst remain individual research labels; no identity equivalence or maliciousness is inferred from them.

`evidence_passages` references `reports` through `reportId`. Each passage contains up to 1,000 text characters, the original catalog URL, title, PDF page number and indexing time. PDF extraction is a timed subprocess, limited to a 20 MiB download, 120 pages and 500,000 text characters. No OCR, downloaded attachments or PDF JavaScript is used. The PDF is temporary; only extracted text and metadata are stored. The BSON size tool includes this new collection.

Literal, case-insensitive search covers report metadata, entity labels, linked indicators and extracted evidence. It preserves punctuation in CVEs, IP addresses, URLs and hashes. It is intended for this local catalog, not an unbounded internet-scale search service. The pre-existing text index remains compatible, but report explorer now uses literal matching. Publisher/year/date filters narrow the result; date filters use UTC publication dates and exclude undated metadata.

Source health exposes the existing importer’s status, warnings and last check. Providers and API credentials are unchanged. A successful source fetch, a keyword topic, a CVE mention and an analyst verdict are separate facts.


## Automatic processing and report-attention levels

`backend.alerts.Processor` processes one catalog PDF at a time. A shared lock serializes bulk and single-report extraction. `reports.processing` stores running/completed/failed state; `import_state` stores the Start/Pause preference. Interrupted running items are eligible again on restart, indexed documents are reused, and failed items need explicit retry. The worker discovers new catalog rows during subsequent cycles. Reports retain separate `triage`, `assessment`, and `alertStatus` fields, so automatic rules never overwrite analyst verdicts or notes.

The triage model is deterministic text rules, with bounded supporting snippets (at most six, 320 characters each). Metadata-only annual publications and fictional scenarios remain unassessed. High/critical textual cues create review alerts, including historical publications; the UI explicitly preserves year/context and does not infer live compromise. Acknowledgement suppresses the open-alert listing without deleting evidence or modifying a manual verdict. Pause this worker as well as discovery when measuring isolated cache behavior.
