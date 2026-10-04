# Deploy Signal Desk to Vercel

This version includes a Flask web entrypoint, a Vercel Python Queue subscriber, password protection, persistent MongoDB job state/results, and a daily source-discovery cron. The local Python server continues to work as before. Vercel Queues is currently a beta service; deployment and live delivery still need verification in your own account.

## 1. Update your existing local Git repository

Download the newest Signal_Desk.zip. Extract its `signal-desk` contents into your existing project folder and replace matching files. Keep the existing `.git` and `.venv` folders. Do not upload the ZIP itself to the repository.

In PowerShell:

```powershell
cd "C:\Users\omnso\Downloads\Signal_Desk\signal-desk"
Get-ChildItem app.py, worker.py, vercel.json, pyproject.toml
git add .
git status
git commit -m "Add Vercel web app and durable report queue"
git push
```

## 2. Create a hosted MongoDB database

1. Sign in to https://cloud.mongodb.com/ and create a project dedicated to Signal Desk.
2. Create a Free cluster if available in your account. A region close to Vercel's configured `iad1` (US East) reduces database latency. Do not select a paid option without checking its price.
3. In Database Access, create a database user with a strong password and `readWrite` permission on **signal_desk**. This is a database login, not your GitHub or Atlas website login.
4. Configure Network Access so connections from your Vercel deployment can reach the cluster. Prefer approved static egress addresses when available. Shared/dynamic egress may require a broader access rule. For an isolated temporary demo cluster, `0.0.0.0/0` permits connection attempts from every IPv4 address: only use it deliberately with the strong, database-scoped credentials above, and remove it after the demo. Adding only your laptop's IP does not allow Vercel to connect.
5. Select Connect → Drivers → Python. Copy the `mongodb+srv://...` connection string and replace its password placeholder locally. URL-encode reserved characters in the username/password if present. Keep TLS and certificate validation enabled.
6. Keep this URI private. It belongs in Vercel environment variables, never source files, Git commits, screenshots, or chat.

The hosted database is separate from your laptop's database. It starts with the bundled catalog; local analyst notes/results are not automatically uploaded. Do not restore an old sample dump over your own saved work.

## 3. Import the GitHub repository in Vercel

1. Sign in to https://vercel.com/ with GitHub.
2. Choose Add New → Project and import **SOLANKYYY/signal-desk**. If the private repository is absent, configure the Vercel GitHub integration to grant access to that repository.
3. Use the repository root (`./`) as Root Directory. `app.py`, `worker.py`, `requirements.txt` and `vercel.json` must be at that root.
4. Select/detect **Flask**, not Next.js. Keep Output Directory unset and use the configuration in `vercel.json`. The build command copies the CSS and JavaScript to `public/`; authenticated HTML is served by Flask.
5. Add the environment variables below before deploying. For an initial production deployment, select the Production environment. Use a separate database such as `signal_desk_preview` if enabling Preview deployments later.

| Name | Value |
|---|---|
| `MONGODB_URI` | Your private Atlas driver connection string |
| `MONGODB_DB` | `signal_desk` |
| `APP_USERNAME` | `admin` |
| `APP_PASSWORD` | A new private password of at least 16 characters for website access |
| `CRON_SECRET` | A random secret of at least 32 characters for daily source discovery |

You can generate independent random values in PowerShell:

```powershell
# Generate a website password; save it in your password manager.
[guid]::NewGuid().ToString("N")

# Generate a different cron secret; paste it into CRON_SECRET.
[guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
```

Do not reuse your GitHub password. No additional Queue API token is required in deployed code; the SDK uses Vercel's deployment identity.

6. Deploy. Keep Fluid compute enabled and the function duration at 300 seconds; the web entrypoint config sets its duration, and generated queue subscribers use the platform's function defaults/settings. If the UI offers Queue beta activation for the project, enable it to use the subscriber.

## 4. Verify the production deployment

- Open the production URL. When the browser prompts, use `admin` and your `APP_PASSWORD`. The static CSS/JavaScript contain no private data; HTML and all application API routes require authentication.
- The first authenticated API request initializes the catalog and indexes. It may take a minute on a new remote database. If setup reports in progress, refresh shortly.
- Confirm **Cloud database connected**, then open **Alerts & threat levels**. The first processing-status request queues the available PDFs; click **Start / resume all** if it was previously paused.
- Check Vercel Queues/Functions logs for the `signal-desk-tasks` topic and generated worker. Confirm indexed/remaining counts change and evidence becomes searchable. Jobs should continue after the browser closes while queue delivery is healthy.
- Test a review and reload the page to verify persistence. Test Pause, wait for the active report to finish, then Resume.
- The daily source check is configured for `0 0 * * *` UTC. Hobby scheduling can be delayed within its scheduled hour. You can also use Check for new reports.
- Check Vercel usage during the initial catalog download. Queue operations and Python function execution consume hosting quotas; do not assume unlimited free processing.

## Optional CLI deployment after project setup

The GitHub import is the simplest first setup. If you prefer the CLI after adding the project and variables:

```powershell
cd "C:\Users\omnso\Downloads\Signal_Desk\signal-desk"
node --version
npm.cmd --version
npm.cmd install --global vercel
vercel.cmd login
vercel.cmd link
vercel.cmd deploy --prod
```

Select the existing Signal Desk project when linking. Avoid creating a second project accidentally. Do not paste credentials into command arguments; add secrets in the Vercel dashboard or its interactive environment-variable prompts.

## What runs locally versus in Vercel

| Capability | Vercel version | Local version |
|---|---|---|
| Feed, filters, reviews, profiles, evidence, alerts | Supported with hosted MongoDB | Supported |
| PDF queue | Durable queue subscriber; saved progress | Local background thread while server runs |
| Source discovery | Daily cron and requested sync jobs | Default 300-second polling |
| Schema sizes and embedded-source alternative | Queued; results saved to MongoDB | Local jobs and JSON files |
| Continuous WiredTiger monitoring | Not enabled; shared database tiers may restrict it | Real counters when permitted |
| 100,000-record generation and randomized reads | Disabled in cloud UI/API | Available locally |

No claimed threat rating or metric is simulated. The website password is a single-user access gate, not a multi-user identity system. Credentials/environment settings and the production deployment must be configured by the account owner.

## Troubleshooting

- **Set APP_PASSWORD / configuration error:** add all required variables to Production, then redeploy. Environment changes require a new deployment.
- **Database connection error:** verify URI/password encoding, active cluster, database user permissions, and network access. Never disable TLS to fix connectivity.
- **Queue startup error:** inspect Vercel build/runtime logs; confirm Queues availability and that `pyproject.toml` registered the `worker` subscriber. The package uses the current Python Queues SDK, which is beta.
- **Processing stalled after a rollout:** click Pause then Start / resume all to publish a fresh chain for the current deployment. Old acknowledged steps are deduplicated; already-indexed PDFs are reused.
- **Job stuck after a platform timeout:** allow up to 12 minutes for queued work, or six minutes after execution starts, then retry. Expired jobs are marked failed in the cloud job listing. Do not repeatedly click a still-running job.
- **PDF failures:** inspect Download failures. Limits remain 20 MiB, 120 pages, 500,000 characters and a 90-second extraction subprocess; unsupported/scanned PDFs remain unassessed.
- **401 on API requests:** sign in through the production homepage with the app password. The cron route instead requires its dedicated bearer secret.

## References

- https://vercel.com/docs/frameworks/backend/flask
- https://vercel.com/docs/queues/python-sdk
- https://vercel.com/docs/queues/pricing
- https://vercel.com/docs/cron-jobs/usage-and-pricing
- https://www.mongodb.com/docs/atlas/tutorial/deploy-free-tier-cluster/
- https://www.mongodb.com/docs/atlas/security/ip-access-list/
