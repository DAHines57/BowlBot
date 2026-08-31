# Restore a logical Postgres dump into the local Docker database.
# Usage (from project root):
#   .\scripts\restore_local_db.ps1                      # newest dump in backups\
#   .\scripts\restore_local_db.ps1 -DumpFile backups\bowlbot_2026-08-05_1248.dump
#   .\scripts\restore_local_db.ps1 -Fetch -RemoteUrl 'postgresql://...'   # dump prod first, then restore
# If execution policy blocks scripts:
#   powershell -ExecutionPolicy Bypass -File .\scripts\restore_local_db.ps1

[CmdletBinding()]
param(
    [string]$DumpFile,
    [switch]$Fetch,
    [string]$RemoteUrl,
    [string]$Container = "bowlbot-db-1",
    [string]$DbUser = "bowlbot",
    [string]$DbName = "bowlbot_dev",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$backups = Join-Path $root "backups"

if ($Fetch) {
    if (-not $RemoteUrl) {
        Write-Error "-Fetch requires -RemoteUrl 'postgresql://...' (the production connection string)."
    }
    $previous = $env:DATABASE_URL
    try {
        $env:DATABASE_URL = $RemoteUrl
        & (Join-Path $root "scripts\backup_db.ps1")
    } finally {
        $env:DATABASE_URL = $previous
    }
}

if ($DumpFile) {
    $dump = Get-Item -Path $DumpFile
} else {
    $dump = Get-ChildItem -Path (Join-Path $backups "*.dump") | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $dump) {
        Write-Error "No .dump files in $backups. Run .\scripts\backup_db.ps1 first, or pass -DumpFile."
    }
}

$running = docker ps --filter "name=^/$Container$" --format "{{.Names}}"
if (-not $running) {
    Write-Error "Container '$Container' is not running. Start it with: docker compose up -d"
}

Write-Host "Restoring $($dump.Name) ($([math]::Round($dump.Length / 1KB, 1)) KB) into $DbName on $Container"
Write-Host "This DROPS the existing '$DbName' database." -ForegroundColor Yellow

if (-not $Force) {
    $answer = Read-Host "Continue? (y/N)"
    if ($answer -notmatch '^(y|yes)$') {
        Write-Host "Aborted."
        return
    }
}

docker cp $dump.FullName "${Container}:/tmp/restore.dump"
if ($LASTEXITCODE -ne 0) { Write-Error "docker cp failed." }

# FORCE terminates lingering app connections that would block the drop.
docker exec $Container psql -U $DbUser -d postgres -v ON_ERROR_STOP=1 `
    -c "DROP DATABASE IF EXISTS $DbName WITH (FORCE);"
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to drop $DbName." }

docker exec $Container psql -U $DbUser -d postgres -v ON_ERROR_STOP=1 `
    -c "CREATE DATABASE $DbName OWNER $DbUser;"
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to create $DbName." }

# Dumps from hosted Postgres reference roles that do not exist locally.
docker exec $Container pg_restore -U $DbUser -d $DbName --no-owner --no-privileges /tmp/restore.dump
if ($LASTEXITCODE -ne 0) { Write-Error "pg_restore failed." }

docker exec $Container rm -f /tmp/restore.dump | Out-Null

$tables = docker exec $Container psql -U $DbUser -d $DbName -t -A `
    -c "select count(*) from information_schema.tables where table_schema = 'public';"
Write-Host "Done. $($tables.Trim()) tables in public schema." -ForegroundColor Green
Write-Host "If your branch has newer migrations, run: alembic upgrade head"
