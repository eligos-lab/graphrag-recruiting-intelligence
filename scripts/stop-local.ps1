$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot ".runtime"
$pgCtl = Join-Path $runtimeRoot "pgvector\Library\bin\pg_ctl.exe"
$pgData = Join-Path $runtimeRoot "postgres-data"

function Stop-ValidatedPort([int]$Port, [string]$ExpectedCommand) {
    $connection = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -eq $connection) {
        return
    }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($connection.OwningProcess)"
    if ($null -eq $process -or $process.CommandLine -notlike "*$ExpectedCommand*") {
        throw "Refusing to stop unexpected process on port $Port"
    }
    Stop-Process -Id $connection.OwningProcess
}

Stop-ValidatedPort 8000 "uvicorn app.main:app"

$workers = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -like "*app.workers.celery_app:celery_app*" -and
    $_.CommandLine -like "*$projectRoot*"
}
foreach ($worker in $workers) {
    Stop-Process -Id $worker.ProcessId
}

Stop-ValidatedPort 7687 "neo4j-community-5.26.29"
Stop-ValidatedPort 6379 "memurai.local.conf"

if ((Test-Path -LiteralPath $pgCtl) -and
    (Test-Path -LiteralPath (Join-Path $pgData "PG_VERSION"))) {
    & $pgCtl -D $pgData stop -m fast
}

Write-Host "GraphRAG services stopped. Ollama remains available for other local applications."
