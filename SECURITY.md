# Security

## Reporting a vulnerability

Do not include credentials, private reports, or exploitable vulnerability details in public issues.

If this repository offers **Security → Report a vulnerability**, use that private reporting channel. If no private channel is available, open a non-sensitive issue asking the maintainer to provide one. Share technical details only after a private channel is agreed.

Include the affected version or commit, expected and actual behavior, impact, and a minimal reproduction. Remove secrets and personal information from logs.

## Operating the application

- Keep the unauthenticated local server on your own machine.
- Configure the hosted application's login credentials and cron secret before use.
- Grant the database user only the permissions needed for the application database. Monitoring experiments may require additional privileges and are intended for a separate local environment.
- Keep connection strings in environment settings, not source files or screenshots.
- Rotate credentials that have been exposed, then update the deployment settings.
- Review Atlas network access and dependency updates regularly.

Automatic report ratings support review; they do not certify a report, URL, file, or system as safe. This project does not provide a security-response SLA or a commitment to backport fixes to older versions.
