param([switch]$Schedule)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)

$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
$dockerPath = if ($dockerCommand) { $dockerCommand.Source } else {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe",
        "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe"
    )
    $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $dockerPath) { throw 'Install Docker Desktop for Windows first.' }
if (-not (Test-Path -LiteralPath '.env')) { throw 'Create .env with scripts/configure.py first.' }
$keyLine = Get-Content -LiteralPath '.env' | Where-Object { $_ -match '^NEWSAPI_KEY=' } | Select-Object -First 1
if (-not $keyLine -or -not $keyLine.Substring(12).Trim()) { throw 'Fill NEWSAPI_KEY in .env and save the file first.' }

function Invoke-Docker {
    & $dockerPath @args
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed (exit $LASTEXITCODE). See output above." }
}

Invoke-Docker info --format '{{.ServerVersion}}'
Invoke-Docker compose config -q
Invoke-Docker compose build collector
Invoke-Docker compose up -d --wait superset
Invoke-Docker compose run --rm collector python collect_news.py
Invoke-Docker compose run --rm collector python verify_database.py
Invoke-Docker compose exec -T superset python /app/pythonpath/verify_dashboard.py
Invoke-Docker compose run --rm collector python export_report.py
if ($Schedule) { Invoke-Docker compose --profile scheduled up -d collector }
Write-Host 'Dashboard: http://localhost:8088/superset/dashboard/tin-tuc-viet-nam/'
Write-Host 'Login: admin. Password: SUPERSET_ADMIN_PASSWORD in your local .env.'
