$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot ".runtime"
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$pgBin = Join-Path $runtimeRoot "pgvector\Library\bin"
$pgData = Join-Path $runtimeRoot "postgres-data"
$memurai = Join-Path $runtimeRoot "memurai\tools\memurai.exe"
$memuraiConfig = Join-Path $runtimeRoot "memurai.local.conf"
$neo4jWrapper = Join-Path $runtimeRoot "start-neo4j.cmd"
$ollama = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"

function Test-LocalPort([int]$Port) {
    return $null -ne (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

foreach ($requiredPath in @($python, $pgBin, $pgData, $memurai, $memuraiConfig, $neo4jWrapper, $ollama)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Missing local runtime component: $requiredPath"
    }
}

if (-not (Test-LocalPort 55432)) {
    & (Join-Path $pgBin "pg_ctl.exe") -D $pgData -l (Join-Path $runtimeRoot "postgres.log") -o '"-p 55432"' start
}

if (-not (Test-LocalPort 6379)) {
    Start-Process -FilePath $memurai -ArgumentList ('"' + $memuraiConfig + '"') `
        -WorkingDirectory (Join-Path $runtimeRoot "memurai-data") -WindowStyle Hidden
}

if (-not (Test-LocalPort 7687)) {
    Start-Process -FilePath $env:COMSPEC -ArgumentList @('/d', '/c', ('"' + $neo4jWrapper + '"')) `
        -WindowStyle Hidden
}

if (-not (Test-LocalPort 11434)) {
    Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $runtimeRoot "ollama.out.log") `
        -RedirectStandardError (Join-Path $runtimeRoot "ollama.err.log")
}

$dependenciesReady = $false
for ($attempt = 0; $attempt -lt 90; $attempt++) {
    if ((Test-LocalPort 55432) -and (Test-LocalPort 6379) -and
        (Test-LocalPort 7687) -and (Test-LocalPort 11434)) {
        $dependenciesReady = $true
        break
    }
    Start-Sleep -Seconds 1
}
if (-not $dependenciesReady) {
    throw "Local dependencies did not become ready in time"
}

Push-Location $projectRoot
try {
    & $python -m alembic upgrade head

    if (-not (Test-LocalPort 8000)) {
        Start-Process -FilePath $python `
            -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info" `
            -WorkingDirectory $projectRoot -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $runtimeRoot "api.out.log") `
            -RedirectStandardError (Join-Path $runtimeRoot "api.err.log")
    }

    $worker = Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -like "*app.workers.celery_app:celery_app*" -and
        $_.CommandLine -like "*$projectRoot*"
    }
    if ($null -eq $worker) {
        Start-Process -FilePath $python `
            -ArgumentList "-m celery -A app.workers.celery_app:celery_app worker --pool=solo --loglevel=INFO" `
            -WorkingDirectory $projectRoot -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $runtimeRoot "worker.out.log") `
            -RedirectStandardError (Join-Path $runtimeRoot "worker.err.log")
    }
}
finally {
    Pop-Location
}

$healthy = $false
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/health" -TimeoutSec 2
        if ($health.status -eq "healthy") {
            $healthy = $true
            break
        }
    }
    catch {}
    Start-Sleep -Seconds 1
}
if (-not $healthy) {
    throw "API did not become healthy; inspect .runtime/api.err.log"
}

Write-Host "GraphRAG is ready"
Write-Host "Swagger UI:    http://localhost:8000/docs"
Write-Host "Health:        http://localhost:8000/api/v1/health"
Write-Host "Neo4j Browser: http://localhost:7474"
