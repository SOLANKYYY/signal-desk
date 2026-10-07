# GitHub setup and update workflow

Repository: https://github.com/SOLANKYYY/signal-desk

Use **VS Code → Terminal → New Terminal → PowerShell** for the commands below. The example creates a fresh clone in `C:\Users\omnso\Projects\signal-desk`, leaving your earlier Downloads copy separate. Use one working copy consistently.

## 1. Clone once

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\Projects" | Out-Null
Set-Location "$env:USERPROFILE\Projects"
gh auth status
gh auth setup-git
git clone https://github.com/SOLANKYYY/signal-desk.git
Set-Location signal-desk
code .
```

If `gh` is not recognized, close and reopen VS Code after installing GitHub CLI. If authentication is missing, run `gh auth login` and choose your SOLANKYYY account. If `code` is unavailable, use VS Code's **File → Open Folder** and select the cloned folder.

If the clone already exists, open it instead of cloning again:

```powershell
Set-Location "$env:USERPROFILE\Projects\signal-desk"
git status
git pull --ff-only origin main
```

Commit or otherwise preserve existing edits before pulling. If Git reports a conflict or divergent branches, stop and inspect the message; do not use force push or reset commands to discard work.

## 2. Apply the documentation package

Extract `Signal_Desk_GitHub_Update.zip` outside the cloned repository. Copy its contents into the clone, merging `.github` and `docs` into existing folders. Replace only matching files in the package; keep all other project files.

This update contains:

| File | Purpose |
| --- | --- |
| `README.md` | Repository landing page, features, tools, setup, and architecture |
| `CONTRIBUTING.md` | Contributor workflow and verification expectations |
| `SECURITY.md` | Security reporting and operation guidance |
| `.github/ISSUE_TEMPLATE/bug_report.md` | Structured bug reports |
| `.github/ISSUE_TEMPLATE/feature_request.md` | Structured feature requests |
| `.github/PULL_REQUEST_TEMPLATE.md` | Pull request description template |
| `docs/GITHUB_WORKFLOW.md` | These GitHub commands and file-editing map |

The package was prepared from the available Signal Desk working version, without authenticated access to the remote repository. Review differences against your clone before committing. It changes documentation and templates only. It does not change the running website or resolve database connectivity.

## 3. Set the GitHub About description and topics

The About text appears on the repository page's right side. You can edit it with the gear icon beside **About**, or run:

```powershell
gh repo edit SOLANKYYY/signal-desk --description "Cyber threat intelligence workspace for security reports, searchable PDF evidence, rule-based alerts, and analyst reviews. Built with Python, Flask, MongoDB, and JavaScript."
gh repo edit SOLANKYYY/signal-desk --add-topic "cyber-threat-intelligence,cybersecurity,python,flask,mongodb,javascript,pdf,vercel"
```

Optional: add the actual deployed homepage when you have verified its URL:

```powershell
$signalDeskUrl = Read-Host "Paste your Signal Desk production HTTPS URL"
gh repo edit SOLANKYYY/signal-desk --homepage "$signalDeskUrl"
```

Do not put a database URI in the homepage field. GitHub's **Languages** panel is calculated from source files; the README's **Technology** section is the place to explain your tools. Topics are searchable labels, not a replacement for the technology table.

## 4. Review and publish the documentation

Run inside the cloned repository:

```powershell
git branch --show-current
git remote -v
git status --short
git diff -- README.md CONTRIBUTING.md SECURITY.md docs/GITHUB_WORKFLOW.md .github
```

The following assumes the current branch is `main`. Untracked files do not appear in the unstaged diff; inspect them in VS Code and review the staged diff below.

```powershell
git add README.md CONTRIBUTING.md SECURITY.md docs/GITHUB_WORKFLOW.md .github/ISSUE_TEMPLATE/bug_report.md .github/ISSUE_TEMPLATE/feature_request.md .github/PULL_REQUEST_TEMPLATE.md
git diff --cached --stat
git diff --cached
git commit -m "docs: improve project overview and contributor workflow"
git push origin main
```

Review the staged diff before committing. If the repository uses another branch name, substitute that name. Branch protection may require a pull request; use the workflow below when direct pushes are restricted.

If Git asks for your identity, set your real name and a verified email or the exact noreply address shown in **GitHub Settings → Emails**. These commands affect this repository only:

```powershell
$signalDeskGitName = Read-Host "Your Git commit name"
$signalDeskGitEmail = Read-Host "Your verified GitHub email or exact GitHub noreply address"
git config user.name "$signalDeskGitName"
git config user.email "$signalDeskGitEmail"
```

Then rerun the commit and push commands.

## 5. Future updates

Before editing, with a clean working tree:

```powershell
git switch main
git pull --ff-only origin main
```

Make and save your changes. For example, after changing the browser interface:

```powershell
git status --short
git diff
git add frontend/index.html frontend/styles.css frontend/app.js
git diff --cached
git commit -m "feat: improve report dashboard"
git push origin main
```

Stage only the files you actually intend to publish. Change the commit message to describe the real update. For behavior changes, run the relevant checks before committing. Never commit secrets or force-push merely to overcome an error.

### Optional branch and pull request workflow

Start before editing:

```powershell
git switch main
git pull --ff-only origin main
git switch -c docs/repository-polish
```

Apply and commit the changes, then:

```powershell
git push -u origin docs/repository-polish
gh pr create --base main --head docs/repository-polish --title "Improve repository documentation" --web
```

Complete the description using the PR template. Review and merge on GitHub when ready. If you already committed the documentation on main but have not pushed, creating this branch at the current commit also allows you to submit that commit as a PR.

## 6. Where to change application behavior

| Desired change | Start here |
| --- | --- |
| Page layout and visible sections | `frontend/index.html` |
| Colors, spacing, responsive layout | `frontend/styles.css` |
| Browser interactions and API calls | `frontend/app.js` |
| Local HTTP behavior | `backend/server.py` |
| Cloud routes and authentication | `backend/web.py` |
| Cloud jobs and initialization | `backend/cloud.py`, `worker.py` |
| Automatic ratings and alerts | `backend/alerts.py` |
| PDF investigation and evidence | `backend/investigation.py`, `backend/pdf_worker.py` |
| Source ingestion | `backend/ingest.py` |
| Database connection and operations | `backend/db.py` |
| Vercel build and configuration | `vercel.json`, `pyproject.toml`, `scripts/vercel_build.py` |
| Python dependencies | `requirements.txt`, `pyproject.toml` |
| Repository description | GitHub About settings or `gh repo edit` |
| Repository documentation | `README.md`, `docs/` |
| Cloud secrets | Vercel project environment settings; never source files |

If Vercel is connected to this repository and `main` is its production branch, pushes to that branch normally trigger deployment according to the project's deployment settings. Check the deployment result in Vercel; a successful Git push does not prove the app or database is healthy.

## 7. Run the cloned app locally

With a local MongoDB service running:

```powershell
Set-Location "$env:USERPROFILE\Projects\signal-desk"
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m backend.server
```

Open http://localhost:8000. A fresh clone needs its own virtual environment. Docker is optional if MongoDB is already running.
