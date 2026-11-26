# Восстановление PostgreSQL из зашифрованной копии, созданной scripts\backup.ps1.
# Останавливает backend на время восстановления, чтобы не держать соединения к СУБД.
# Запуск: powershell -ExecutionPolicy Bypass -File scripts\restore.ps1 -Archive database\backups\daily\crisis-analytics-....dump.enc
param(
    [Parameter(Mandatory = $true)]
    [string]$Archive
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Read-DotEnvValue([string]$Name) {
    $path = Join-Path $root ".env"
    if (-not (Test-Path $path)) { return $null }
    foreach ($line in Get-Content -Path $path -Encoding UTF8) {
        if ($line -match "^$Name=(.*)$") { return $Matches[1] }
    }
    return $null
}

if (-not $env:BACKUP_ENCRYPTION_KEY) {
    $env:BACKUP_ENCRYPTION_KEY = Read-DotEnvValue "BACKUP_ENCRYPTION_KEY"
}
if (-not $env:BACKUP_ENCRYPTION_KEY -or $env:BACKUP_ENCRYPTION_KEY.Length -lt 32) {
    throw "Задайте BACKUP_ENCRYPTION_KEY (не короче 32 символов) в окружении или в .env"
}

$archivePath = Resolve-Path $Archive
$work = Join-Path $root "database\backups\work"
New-Item -ItemType Directory -Force -Path $work | Out-Null
$plain = Join-Path $work "restore.dump"

docker compose run --rm --no-deps --entrypoint python `
    -e BACKUP_ENCRYPTION_KEY=$env:BACKUP_ENCRYPTION_KEY `
    -v "$(Split-Path -Parent $archivePath):/in:ro" `
    -v "${work}:/work" `
    backend -m app.ops.backup_archive decrypt --input "/in/$(Split-Path -Leaf $archivePath)" --output /work/restore.dump
if ($LASTEXITCODE -ne 0) { throw "Расшифровка резервной копии не выполнена" }

Write-Host "Останавливаю backend на время восстановления."
docker compose stop backend | Out-Null
try {
    docker compose cp $plain "database:/tmp/restore.dump"
    if ($LASTEXITCODE -ne 0) { throw "Не удалось скопировать дамп в контейнер СУБД" }
    docker compose exec -T database sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner /tmp/restore.dump'
    $restoreCode = $LASTEXITCODE
    docker compose exec -T database rm -f /tmp/restore.dump | Out-Null
    if ($restoreCode -ne 0) {
        throw "pg_restore завершился с кодом $restoreCode. Предупреждения pg_restore тоже дают ненулевой код; проверьте журнал контейнера database."
    }
}
finally {
    Remove-Item -Force $plain -ErrorAction SilentlyContinue
    docker compose start backend | Out-Null
}

Write-Host "Восстановление завершено. Проверьте схему: docker compose exec backend python -m app.db.setup"
