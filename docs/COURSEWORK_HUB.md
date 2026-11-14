# Signal Desk command center and coursework hub

The main workspace combines threat intelligence, source evidence, investigation cases and an Experiments 11–18 hub at `/#labs`. Earlier report/replica/write-concern interfaces remain at `/laboratory`. The navy/cyan design supports dark and light modes and single-column mobile cards.

Each experiment has its own Docker Hub repository link and reference chapter. The owner has reported completion. Until result JSON is imported, cards explicitly say **Completion reported**, not verified. Repository links are targets; this page does not claim a live registry check.

## Import results

Open the experiment hub, choose a card's **Import results**, select compact JSON files from that kit's `results` folder and submit. Imports replace only the selected experiment's previous evidence. Existing report, threat and earlier-lab collections are unchanged. JSON is kept in `coursework_evidence` with its import timestamp and canonical SHA-256 for each file. Imported documents can be downloaded again.

A card says **Imported: reports pass** only when every imported file explicitly has boolean `passed: true` at its root. Other valid result files show **Evidence imported**. This is a record of submitted output, never an independently rerun test. PDF reports and screenshots remain in the original submission kits; they are not uploaded by this form.

Uploads are authenticated by the existing app gate, restricted to same-origin writes, bounded to 950 KB and 15 files, and reject mismatched experiment numbers and obvious secret material. Do not upload `.env`, credentials, tokens or TLS private keys. The catalogue remains readable if evidence storage is unavailable.

## Verification

Unit and HTTP contract tests cover distinct repository links, import replacement scope, export, pass-label semantics, experiment mismatches, secret rejection, size limits, database outage fallback, authentication and cross-origin rejection. Existing tests cover threat APIs and earlier lab functions.
