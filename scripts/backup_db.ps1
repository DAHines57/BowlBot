# Logical Postgres backup using DATABASE_URL from the current shell.
# Usage (from project root, DATABASE_URL set in this shell):
#   .\scripts\backup_db.ps1
# If execution policy blocks scripts:
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
#   # or: powershell -ExecutionPolicy Bypass -File .\scripts\backup_db.ps1

$ErrorActionPreference = "Stop"

if (-not $env:DATABASE_URL) {
    Write-Error "Set DATABASE_URL first, e.g. `$env:DATABASE_URL = 'postgresql://...'"
}

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$backups = Join-Path $root "backups"
New-Item -ItemType Directory -Force -Path $backups | Out-Null

$ts = Get-Date -Format "yyyy-MM-dd_HHmm"
$out = Join-Path $backups "bowlbot_$ts.dump"

Write-Host "Backing up to $out ..."

$pgDump = Get-Command pg_dump -ErrorAction SilentlyContinue
if ($pgDump) {
    & pg_dump $env:DATABASE_URL -Fc -f $out
} else {
    # pg_dump major version must match the server (Railway may use PG 18).
    $mount = "${backups}:/backups"
    docker run --rm `
        -e DATABASE_URL=$env:DATABASE_URL `
        -v $mount `
        postgres:18-alpine `
        sh -c "pg_dump `"`$DATABASE_URL`" -Fc -f /backups/bowlbot_$ts.dump"
}

$size = (Get-Item $out).Length
Write-Host "Done. Size: $([math]::Round($size / 1KB, 1)) KB -> $out"
