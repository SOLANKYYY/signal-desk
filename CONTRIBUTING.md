# Contributing to Signal Desk

Keep changes focused and explain the problem they solve. For a substantial feature, open an issue describing the intended behavior before implementation.

## Setup

Follow the README to create a Python virtual environment and configure MongoDB. Install development dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## Make a change

Start from an up-to-date checkout and create a descriptive branch:

```powershell
git switch main
git pull --ff-only origin main
git switch -c feature/report-filter
```

Use `frontend/` for interface changes, `backend/` for API and processing behavior, and `docs/` for documentation. Preserve saved analyst decisions when changing ingestion or schema behavior. Keep fictional content clearly labelled and keep automatic ratings distinct from analyst verdicts.

For behavior changes, run the relevant checks and the Python suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

For interface changes, check both narrow and wide layouts, keyboard interaction, loading states, and errors. Documentation-only changes require a review of commands and links rather than unrelated runtime tests.

## Submit

Review `git diff`, stage the intended files explicitly, and use a concise commit message describing the change. In a pull request, explain the problem, resulting behavior, verification performed, and any deployment steps. Use screenshots only when they represent the current change.

Do not commit passwords, tokens, private reports, environment files, virtual environments, or generated database output. Do not replace measured values with invented metrics. Report security concerns according to SECURITY.md.
