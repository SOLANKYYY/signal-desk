# Signal Desk — Exercise 9 Docker kit

This kit implements the Classroom screenshot's Lab 9.1, journaling comparison, and Lab 9.2. It records actual measurements, never expected values. It is separate from Chapter 8 and from Signal Desk's production database. No host MongoDB ports are published. Keep Docker Desktop running in Linux-container mode. You do not need Python on Windows.

## 1. Start the lab

Extract the whole ZIP. Open `SignalDesk_Exercise9` in VS Code, then open a PowerShell terminal **in that folder**. Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

The execution policy override is scoped to this one PowerShell process. The script builds the Python image and starts `sd9-mongo1`, `sd9-mongo2`, and `sd9-mongo3` on `signal-desk-exercise9-net`. It initializes replica set `sd9`. There is no arbiter: the voting majority is two and all data-bearing members means three. It does not touch the Chapter 8 containers or volumes.

## 2. Lab 9.1 and Try It Yourself

Before running, write your prediction of the fastest concern and journal overhead. Then:

```powershell
docker compose run --rm -T python latency
```

Wait for all six table rows (journal waits can take several minutes). The script inserts 1,000 small documents per configuration, measuring each insert with `time.perf_counter`. A separate warm-up insert is excluded. It records total elapsed time, per-write timings, the MongoDB version, and majority journal setting. Any failed benchmark insert stops the run; an incomplete benchmark is not exported as successful. Results from an earlier successful run remain, so check their timestamps before uploading.

Output: `results/lab_9_1_latency.json`.

- `w:1`: primary acknowledgment.
- `w:majority`: two voting data-bearing members in this topology.
- The assignment's “w:all” is implemented as **w:3**. MongoDB has no built-in `"all"` mode; a string other than `"majority"` would need a custom configured mode.
- Each concern runs with explicit `j:false` and `j:true`.
- `j:false` does not disable background journaling. MongoDB 7's default `writeConcernMajorityJournalDefault:true` can make majority writes wait for journal durability even with `j:false`. Do not promise a fixed speedup or ordering.
- P50 is the median; P99 is nearest rank. Average is mean per-write duration, and total also includes loop overhead. Six cases run sequentially, so cache, background activity and order may affect results. Explain what you observe instead of replacing measurements with theoretical expectations.

## 3. Lab 9.2 — network partition

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run-partition.ps1
```

This script checks a healthy baseline, discovers the actual primary, disconnects one secondary for at least 30 seconds, probes `w:1` and `w:majority`, and samples the original primary's `rs.status()` view. It reconnects and verifies catch-up with a `w:3` sentinel read on all three members. It then discovers the primary again, disconnects **both** secondaries for 30 seconds, repeats probes/observations, restores networking, and verifies final recovery. Finally it saves `results/lab_9_2_partition.json`.

The Python client disables retryable writes to expose individual probe results. A 2-second write concern timeout bounds acknowledgment waits; separate selection/connection/socket timeouts bound observation failures. Depending on election timing, a probe may return a write-concern timeout, a not-primary error, or another connection error. These are recorded honestly. A write concern timeout does not roll back the write. After the isolated primary steps down, `w:1` also fails. Write concern alone does not define a CP/AP classification or provide linearizable reads.

The timeline shows sampled states from the observer, not an exact internal step-down time. Repeated snapshots are collapsed on the website; all samples remain in the JSON. `partition-progress.json` and `partition-plan.json` are temporary evidence, not the files to upload.

The PowerShell `finally` block restores networking on ordinary script errors. If you close the terminal or Docker stops unexpectedly, run these recovery commands; “already exists” means that node is already connected:

```powershell
docker network connect --alias sd9-mongo1 signal-desk-exercise9-net sd9-mongo1
docker network connect --alias sd9-mongo2 signal-desk-exercise9-net sd9-mongo2
docker network connect --alias sd9-mongo3 signal-desk-exercise9-net sd9-mongo3
docker compose run --rm -T python init
```

Then rerun `run-partition.ps1` to record a complete experiment. Never disconnect your production MongoDB or Chapter 8 nodes for this exercise.

## 4. Update Signal Desk

Open **Exercise 9 · Write concern → Upload results**. Select the two generated files from `results`, together or one at a time. The app stores recorded evidence; Docker does not have to stay running to view it. Each import replaces the previous evidence for that activity. The page calculates latency summaries from the uploaded samples, displays write outcomes, and shows election/recovery states. These are user-uploaded records, not independently attested measurements.

## 5. Docker Hub and Classroom submission

Do this after both result JSON files exist. Replace `YOUR_DOCKERHUB_USERNAME` with your actual username:

```powershell
docker build -f Dockerfile.submission -t YOUR_DOCKERHUB_USERNAME/signal-desk-exercise9:exercise9 .
docker login
docker push YOUR_DOCKERHUB_USERNAME/signal-desk-exercise9:exercise9
```

This submission image includes the runnable Python scripts, the kit under `/kit`, and your two measured JSON files under `/evidence`. Do not include credentials or Signal Desk's `.env` file. Make the Docker Hub repository public if required for your instructor to pull it. Enter `https://hub.docker.com/r/YOUR_DOCKERHUB_USERNAME/signal-desk-exercise9` on Signal Desk's Exercise 9 page, add your explanation, and choose **Print submission report / Save as PDF**. Upload that PDF in Classroom. The page does not push images, verify Docker Hub publication, or submit coursework for you.

### Demonstrate using the published image

On the demonstration machine, with Docker Desktop running:

```powershell
docker pull YOUR_DOCKERHUB_USERNAME/signal-desk-exercise9:exercise9
docker create --name sd9-submission-extract YOUR_DOCKERHUB_USERNAME/signal-desk-exercise9:exercise9
docker cp sd9-submission-extract:/kit ./Exercise9_Demo
docker cp sd9-submission-extract:/evidence ./Exercise9_Evidence
docker rm sd9-submission-extract
cd ./Exercise9_Demo
$env:LAB_IMAGE = 'YOUR_DOCKERHUB_USERNAME/signal-desk-exercise9:exercise9'
New-Item -ItemType Directory -Force ./results
docker compose up -d sd9-mongo1 sd9-mongo2 sd9-mongo3
docker compose run --rm -T python init
docker compose run --rm -T python latency
powershell -NoProfile -ExecutionPolicy Bypass -File .\run-partition.ps1
```

These commands use the pulled image for the exercises; do not run `start.ps1` in this demonstration flow because it rebuilds the image. The evidence extracted in `Exercise9_Evidence` is the original submission; fresh demonstration evidence goes into `Exercise9_Demo/results`.

After finishing, preserve results and stop the kit:

```powershell
docker compose stop
```

## Sources and verification limits

Assignment reference: https://github.com/sujeetjagtap/NoSQL-Databases-using-MongoDB/tree/main/chapter-09

MongoDB 7 semantics: https://www.mongodb.com/docs/v7.0/reference/write-concern/

Docker network restoration: https://docs.docker.com/reference/cli/docker/network/connect/

The app's validation and route tests use isolated mock storage. Docker and PowerShell are not available in the development environment used to prepare this kit. A successful local run of both exercises is still required before calling Exercise 9 complete.
