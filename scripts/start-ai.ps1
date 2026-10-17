param([switch]$Schedule, [switch]$SyncAdminPassword)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
$dockerPath = if ($dockerCommand) { $dockerCommand.Source } else {
    @("$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe", "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe") |
        Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $dockerPath) { throw 'Docker Desktop was not found.' }
if (-not (Test-Path -LiteralPath '.env')) { throw 'Create .env first.' }
function Invoke-Docker {
    & $dockerPath @args
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed (exit $LASTEXITCODE)." }
}
Invoke-Docker info --format '{{.ServerVersion}}'
Invoke-Docker compose --profile ai config -q
Invoke-Docker compose --profile ai build analytics
Invoke-Docker compose up -d --wait --no-deps postgres
$initialized = & $dockerPath compose exec -T postgres psql -U news -d superset_meta -Atc "SELECT count(*) FROM dashboards WHERE slug='tin-tuc-viet-nam'"
if ($LASTEXITCODE -ne 0 -or $initialized -ne '1') { Invoke-Docker compose run --rm superset-init }
Invoke-Docker compose up -d --wait --no-deps superset
$credentialArgs = @('compose', 'exec', '-T', 'superset', 'python', '/app/pythonpath/check_admin_credentials.py')
if ($SyncAdminPassword) { $credentialArgs += '--sync-password' }
Invoke-Docker @credentialArgs
Invoke-Docker compose --profile ai run --rm analytics python -m analytics.pipeline
Invoke-Docker compose --profile ai run --rm analytics python -m analytics.verify_mcp
if ($Schedule) { Invoke-Docker compose --profile ai up -d ai-worker }
Write-Host 'TH2: http://localhost:8088/superset/dashboard/tin-tuc-ai-th2/'
Write-Host 'Report: output/th2/BAO_CAO_KY_THUAT.md'
Write-Host 'No Gemini key: pipeline records waiting_key; sentiment charts stay empty.'
