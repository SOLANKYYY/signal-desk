$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force ./results | Out-Null
& docker compose build python
if ($LASTEXITCODE -ne 0) { throw 'Docker image build failed. Start Docker Desktop and retry.' }
& docker compose up -d sd9-mongo1 sd9-mongo2 sd9-mongo3
if ($LASTEXITCODE -ne 0) { throw 'Could not start the Exercise 9 containers.' }
& docker compose run --rm -T python init
if ($LASTEXITCODE -ne 0) { throw 'Replica set initialization failed.' }
