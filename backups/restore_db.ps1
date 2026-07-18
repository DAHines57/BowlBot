# Restore a logical Postgres dump into local Docker Postgres (bowlbot_dev).
# Usage (from project root):
#   .\backups\restore_db.ps1                          # latest dump
#   .\backups\restore_db.ps1 bowlbot_2026-07-14_0712.dump
#   .\backups\restore_db.ps1 -List
# If execution policy blocks scripts:
#   powershell -ExecutionPolicy Bypass -File .\backups\restore_db.ps1

param(
    [Parameter(Position = 0)]
    [string]$Dump,

    [switch]$List,

    [switch]$SkipMigrate
)

$ErrorActionPreference = "Stop"

$backupsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $backupsDir
$dumps = @(Get-ChildItem -Path $backupsDir -Filter "*.dump" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending)

if ($List) {
    if ($dumps.Count -eq 0) {
        Write-Host "No .dump files in $backupsDir"
        exit 0
    }
    Write-Host "Dumps in $backupsDir (newest first):"
    foreach ($d in $dumps) {
        $kb = [math]::Round($d.Length / 1KB, 1)
        Write-Host ("  {0}  {1} KB  {2}" -f $d.Name, $kb, $d.LastWriteTime.ToString("yyyy-MM-dd HH:mm"))
    }
    exit 0
}

if (-not $Dump) {
    if ($dumps.Count -eq 0) {
        Write-Error "No .dump files found in $backupsDir. Run .\scripts\backup_db.ps1 first."
    }
    $Dump = $dumps[0].Name
    Write-Host "Using latest dump: $Dump"
}

$dumpPath = if ([System.IO.Path]::IsPathRooted($Dump)) { $Dump } else { Join-Path $backupsDir $Dump }
if (-not (Test-Path $dumpPath)) {
    Write-Error "Dump not found: $dumpPath"
}
$dumpFile = Split-Path -Leaf $dumpPath

# Local defaults (matches docker-compose.yml)
$localUrl = "postgresql://bowlbot:bowlbot@localhost:5432/bowlbot_dev"
if (-not $env:DATABASE_URL) {
    $env:DATABASE_URL = $localUrl
    Write-Host "DATABASE_URL not set; using local: $localUrl"
}

$url = $env:DATABASE_URL
$isLocal = $url -match 'localhost|127\.0\.0\.1|host\.docker\.internal'
if (-not $isLocal) {
    Write-Error @"
Refusing to restore: DATABASE_URL does not look local.
Current: $url

Unset it or set local first:
  `$env:DATABASE_URL = '$localUrl'
"@
}

Write-Host "Target: $url"
Write-Host "Dump:   $dumpPath"
Write-Host ""
Write-Host "This DROPS and recreates bowlbot_dev, then restores the dump."
$confirm = Read-Host "Type YES to continue"
if ($confirm -ne "YES") {
    Write-Host "Aborted."
    exit 1
}

Push-Location $root
try {
    Write-Host "Ensuring local Postgres is up..."
    docker compose up -d db | Out-Host

    # Wait briefly for readiness
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        docker compose exec -T db pg_isready -U bowlbot -d postgres 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $ready = $true
            break
        }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) {
        Write-Error "Postgres did not become ready. Is Docker Desktop running?"
    }

    Write-Host "Recreating bowlbot_dev..."
    docker compose exec -T db psql -U bowlbot -d postgres -c "DROP DATABASE IF EXISTS bowlbot_dev WITH (FORCE);" | Out-Host
    docker compose exec -T db psql -U bowlbot -d postgres -c "CREATE DATABASE bowlbot_dev;" | Out-Host

    Write-Host "Restoring..."
    $pgRestore = Get-Command pg_restore -ErrorAction SilentlyContinue
    if ($pgRestore) {
        & pg_restore -d $url --no-owner --no-acl --verbose $dumpPath
        # pg_restore often exits 1 on non-fatal warnings; treat missing dump as hard fail above
        if ($LASTEXITCODE -gt 1) {
            Write-Error "pg_restore failed with exit code $LASTEXITCODE"
        }
    } else {
        # Rewrite localhost so the container can reach compose Postgres on the host.
        $dockerUrl = $url -replace '://([^/@]+)@(localhost|127\.0\.0\.1):', '://$1@host.docker.internal:'
        $mount = "${backupsDir}:/backups"
        docker run --rm `
            -v $mount `
            postgres:18-alpine `
            pg_restore `
            -d $dockerUrl `
            --no-owner --no-acl `
            "/backups/$dumpFile"
        if ($LASTEXITCODE -gt 1) {
            Write-Error "docker pg_restore failed with exit code $LASTEXITCODE"
        }
    }

    if (-not $SkipMigrate) {
        $alembic = Get-Command alembic -ErrorAction SilentlyContinue
        if ($alembic) {
            Write-Host "Running alembic upgrade head..."
            & alembic upgrade head
        } else {
            Write-Host "alembic not on PATH; skip migrate (or activate your venv and run: alembic upgrade head)"
        }
    }

    Write-Host "Done. Local DB restored from $dumpFile"
    Write-Host "App URL tip: `$env:DATABASE_URL = '$localUrl'"
}
finally {
    Pop-Location
}
