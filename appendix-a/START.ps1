$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
function Invoke-Docker { & docker @args; if ($LASTEXITCODE -ne 0) { throw 'Docker step failed. Stop here and inspect the output.' } }
if (-not (Test-Path .env)) {
  $bytes = New-Object byte[] 24
  $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
  $rng.GetBytes($bytes); $rng.Dispose()
  $password = [Convert]::ToBase64String($bytes)
  $text = "APP_USERNAME=admin`nAPP_PASSWORD=$password`n"
  [IO.File]::WriteAllText((Join-Path $PSScriptRoot '.env'), $text, (New-Object Text.UTF8Encoding($false)))
}
Invoke-Docker compose -f compose.yml up -d mongo ollama
$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
  & docker compose -f compose.yml exec -T ollama ollama list *> $null
  if ($LASTEXITCODE -eq 0) { $ready = $true; break }
  Start-Sleep -Seconds 2
}
if (-not $ready) { throw 'Ollama did not become ready. Check docker compose -f compose.yml logs ollama.' }
Invoke-Docker compose -f compose.yml exec -T ollama ollama pull llama3.2:3b
Invoke-Docker compose -f compose.yml exec -T ollama ollama pull nomic-embed-text
Invoke-Docker compose -f compose.yml up -d --build app
Write-Host 'Open http://localhost:8019/#assistant'
Write-Host 'Username: admin. Your generated password is in appendix-a/.env. Do not upload that file.'
Write-Host 'Add an advisory excerpt in Knowledge Workspace, or import existing feed events after syncing them.'
Write-Host 'First model downloads need several GB of free disk space. Keep other lab containers stopped if memory is limited.'
