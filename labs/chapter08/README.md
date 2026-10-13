# Chapter 8 in Signal Desk

Signal Desk → **Replica Set Lab** displays the results of the four Docker experiments. It shows the roles and health recorded at the end of a run, replication checks, primary changes, read successes/failures, election predictions, and expandable command evidence.

**Recorded evidence, not a live monitor.** A healthy snapshot does not mean the containers are currently running. Vercel cannot start or stop Docker on your laptop. Run the experiments locally, then upload their JSON output. No Docker connection or additional Vercel environment variable is needed for this page. It uses Signal Desk's existing authenticated API and MongoDB connection.

## Your experiments are already finished

You can use the JSON files generated in your existing `Chapter_08_Submission` folders. You do not need to rerun the experiments just to display them.

After deploying the updated Signal Desk:

1. Open **Replica Set Lab** in the sidebar.
2. Choose a result JSON file, then click **Upload results**. Files from different folders can be uploaded one at a time.
3. Repeat for the other activities listed below. You can also select up to four files in one upload.
4. Select an activity card to see member roles, election changes and evidence.
5. After a later experiment, upload its new JSON file. **Reload saved results** reloads stored evidence; it does not run an experiment.

| Activity folder | Upload this generated file |
| --- | --- |
| Activity_8.1 | lab_8_1_replica_set.json |
| Activity_8.1_Try_It_Yourself | try_8_1_add_arbiter.json |
| Activity_8.2 | lab_8_2_failover_monitor.json |
| Activity_8.2_Try_It_Yourself | try_8_2_priority_election.json |

The page starts empty. No old ZIP results or terminal transcripts are seeded into the database. Upload your newly generated JSON files rather than the original example outputs.

## Run again from this repository (optional)

Install and open Docker Desktop with Linux containers. In VS Code, open a PowerShell terminal at the Signal Desk repository root. Docker installs MongoDB and the Python dependencies; no host Python installation is needed for the labs.

All four Compose files use the same project and database volumes. Each maps mongo1 to host port **27117**, mongo2 to **27018** and mongo3 to **27019**. Internal MongoDB ports remain **27017**. These are local unauthenticated teaching containers bound to loopback. Do not expose them to the internet or point the lab scripts at your production CTI database.

### 1. Replication

```powershell
cd .\labs\chapter08\Activity_8.1
docker compose up -d
docker compose run --rm python lab_8_1_replica_set.py
```

This initialization script expects three data-bearing members. On an existing lab that already has an arbiter, skip this initialization run and retain its earlier JSON result; continue with the remaining activities. Do not delete existing volumes just to regenerate this file.

### 2. Arbiter

```powershell
cd ..\Activity_8.1_Try_It_Yourself
docker compose --profile arbiter up -d
docker compose run --rm python try_8_1_add_arbiter.py
```

### 3. Failover

```powershell
cd ..\Activity_8.2
docker compose --profile arbiter up -d
docker compose run --rm python lab_8_2_failover_monitor.py
```

### 4. Election priorities

```powershell
cd ..\Activity_8.2_Try_It_Yourself
docker compose --profile arbiter up -d
docker compose run --rm python try_8_2_priority_election.py
```

Wait for the prompt to return. The priority experiment deliberately waits for an election restriction to expire. Results depend on your actual run; successful reads and election timings are not fixed values.

To stop the containers while keeping data:

```powershell
docker compose --profile arbiter stop
```

## Deployment and data storage

Merge the feature branch into the Git branch connected to your Signal Desk Vercel project. If automatic Git deployments are enabled, Vercel will build the change. Otherwise redeploy that commit from Vercel. The target must use this repository's Flask app (`app.py`), not the separate CTI Verify React deployment.

Existing `MONGODB_URI`, `MONGODB_DB`, `APP_USERNAME` and `APP_PASSWORD` settings continue to apply. The existing MongoDB user needs read/write permission for `replica_lab_runs` in the configured Signal Desk database. The first upload creates this collection automatically. Its built-in unique `_id` index supports all lookups; no additional indexes are required.

- `GET /api/replica-lab`: four activity cards with latest uploaded summaries.
- `POST /api/replica-lab/import`: one JSON result document, maximum 1 MiB and 500 steps.
- `GET /api/replica-lab/{id}`: saved summary and original evidence; IDs are `replication`, `arbiter`, `failover`, `priorities`.

Storage is bounded to one uploaded result per activity, four documents total. Uploading again replaces that activity's prior evidence. Each document stores a normalized summary, original Extended JSON as text, upload time and a checksum. The checksum identifies the uploaded content; it does not independently authenticate the experiment.

Evidence is user supplied and never executed. Commands including `replSetReconfig` and `replSetStepDown` only appear as text. No production replica-set controls, Docker socket, public laptop port, or database administrative permission is required by the web feature.

## Validation

Run `python -m unittest discover -s tests` after installing `requirements-dev.txt`. Replica feature tests use isolated in-memory MongoDB mocks. Live MongoDB persistence and Vercel deployment must still be checked in your configured environment.
