# Data provenance

Snapshot retrieved 2026-09-30 from the assignment's public GitHub README:
https://github.com/jacobdjwilson/awesome-annual-security-reports

Contains 465 distinct annual-report references: titles, publishers, years and links only. No report PDFs, full articles, or repository summaries are redistributed. These are catalog entries, not validated threat incidents; follow the original links to assess claims. Snapshot retrieval is not evidence of publication accuracy or link availability.

CTI Digest (https://ctidigest.com/) inspired the news / source / IOC schema. Direct automated retrieval returned HTTP 403 during preparation. The seed does not claim to contain an authentic CTI Digest database dump. Five original fictional scenarios use reserved example.invalid domains and are clearly tagged synthetic. Live ingestion tries public article HTML and discovered RSS/Atom feeds and reports failure explicitly.

The 100,000 lab documents are generated workload records derived from these metadata references, NOT 100,000 distinct genuine reports. Each is padded to exactly 2,048 BSON bytes and marked synthetic.


## Public threat snapshot — 13 November 2026
`public-threat-snapshot.json.gz` contains 15,000 genuine published MISP indicator attributes selected from 19,734 unique attributes collected from 20 public CIRCL/Botvrij feed events. The latest-modification selection contains five events from three reporting organizations, all mirrored through CIRCL. Most selected attributes come from one publisher; this is not a representative global threat sample. Attribute UUIDs, original event URLs, provenance and timestamps are preserved. These are feed claims, not verified attacks or victims. No malware files were downloaded.

First explicit dashboard feed sync imports this snapshot into the application's threat collections, then fetches changed events from both feeds. Existing report reviews and generated coursework data remain separate.
