# Laptop checks inside Ask Signal Desk

This feature explains a small, user-uploaded Windows security snapshot in the existing chatbot. It does not run commands on a visitor's laptop, inspect arbitrary uploaded files, perform a vulnerability scan, or certify whether an attack is in progress.

## Use

1. Sign in, open **Ask Signal Desk**, then **Check my laptop** inside the question form.
2. Download and inspect `Collect-SignalDeskCheck.ps1`. Run it locally from Windows PowerShell with `./Collect-SignalDeskCheck.ps1`. If an organization policy blocks scripts, ask the administrator; do not disable system-wide protections. Some checks require administrator privileges. Unavailable checks are explicitly marked unknown.
3. Review the generated `SignalDesk-Device-Check-*.json`. Attach it in the same chat form, preview it, and confirm permission to share.
4. Ask “What needs attention, and does this show evidence of threats?” Read the fixed findings card and the AI explanation. Follow-up questions in that conversation reuse its snapshot. Start a new conversation for another device.

The script reads Defender protection status, signature/scan age, Defender active/history counts, configured firewall profile states, last visible hotfix date, Secure Boot, system-drive BitLocker protection and the Remote Desktop setting. It writes one local JSON file and makes no network requests or setting changes. It excludes device identity, usernames, IPs, file paths/contents, detection resource paths, passwords and recovery keys.

## Interpretation

- An active Defender record is reported as a Defender detection needing review; it does not identify a live attacker.
- Historical detections do not prove a current infection. Zero detections cannot prove a clean device.
- Disabled protection is a configuration finding. Defender may be disabled when another antivirus manages the device; a disabled firewall profile may not currently be in use.
- Signature age over 7 days and a hotfix older than 45 days are review heuristics, not vendor compliance rules. Get-HotFix is not complete update inventory and cannot establish a CVE or missing patch.
- Missing permissions, unsupported features and absent fields are unknown, never passes. Reports older than 7 days are labelled historical.

## Data handling

Only the generated JSON schema is supported, up to 64 KB. A positive consent flag is required. The server validates field types, ranges and timestamps, drops unrecognized fields, and derives findings before calling the model. It never executes uploaded content. Raw uploaded files and filenames are not saved. Only the normalized assessment and conversation are stored in `chat_turns`; no laptop data is added to `chat_chunks` or global retrieval. The hosted model receives the normalized assessment as source [1], together with the question and recent conversation. Deterministic findings display before AI generation and remain visible if generation fails; incomplete answers are not saved.

The application uses one shared login, not per-person private accounts. Anyone using it can see saved conversations. Consent in the upload form explains this. Use minimal authorized snapshots only. The site uses its configured provider (currently Gemini); the Docker version uses local Ollama unless reconfigured. The previous published Docker image does not acquire this feature automatically: rebuild and push after updating its app source.

## Verification

Unit tests cover input validation, privacy field exclusion, active vs historical detections, stale/unknown findings, consent, per-conversation follow-ups, authenticated download/upload and body limits. PowerShell fixture tests exercise the collector without reading the developer's actual device. These tests do not establish real endpoint-security coverage or live AI accuracy.

## Microsoft references

- [Get-MpComputerStatus](https://learn.microsoft.com/powershell/module/defender/get-mpcomputerstatus)
- [Get-MpThreat](https://learn.microsoft.com/powershell/module/defender/get-mpthreat)
- [Get-NetFirewallProfile](https://learn.microsoft.com/powershell/module/netsecurity/get-netfirewallprofile)
