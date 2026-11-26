# Резервная копия PostgreSQL: pg_dump -Fc, шифрование AES-256-GCM, ротация.
# 7 последних ежедневных копий и 4 еженедельные (копия по воскресеньям UTC).
# Ключ: BACKUP_ENCRYPTION_KEY в окружении или в .env (не короче 32 символов).
# Запуск из любого каталога: powershell -ExecutionPolicy Bypass -File scripts\backup.ps1
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

$daily = Join-Path $root "database\backups\daily"
$weekly = Join-Path $root "database\backups\weekly"
$work = Join-Path $root "database\backups\work"
New-Item -ItemType Directory -Force -Path $daily, $weekly, $work | Out-Null

$stamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$plain = Join-Path $work "dump.bin"
$encryptedName = "crisis-analytics-$stamp.dump.enc"
$dumpInContainer = "/tmp/crisis-analytics.dump"

docker compose exec -T database sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/crisis-analytics.dump'
if ($LASTEXITCODE -ne 0) { throw "pg_dump завершился с кодом $LASTEXITCODE" }
docker compose cp "database:${dumpInContainer}" $plain
if ($LASTEXITCODE -ne 0) { throw "Не удалось скопировать дамп из контейнера СУБД" }
docker compose exec -T database rm -f $dumpInContainer | Out-Null

docker compose run --rm --no-deps --entrypoint python `
    -e BACKUP_ENCRYPTION_KEY=$env:BACKUP_ENCRYPTION_KEY `
    -v "${work}:/work:ro" `
    -v "${daily}:/daily" `
    backend -m app.ops.backup_archive encrypt --input /work/dump.bin --output "/daily/$encryptedName"
if ($LASTEXITCODE -ne 0) { throw "Шифрование резервной копии не выполнено" }
Remove-Item -Force $plain

$encrypted = Join-Path $daily $encryptedName
if ((Get-Date).ToUniversalTime().DayOfWeek -eq [DayOfWeek]::Sunday) {
    Copy-Item -Force $encrypted (Join-Path $weekly $encryptedName)
}

docker compose run --rm --no-deps --entrypoint python -v "${daily}:/daily" backend -m app.ops.backup_archive rotate --dir /daily --keep 7
if ($LASTEXITCODE -ne 0) { throw "Ротация ежедневных копий не выполнена" }
docker compose run --rm --no-deps --entrypoint python -v "${weekly}:/weekly" backend -m app.ops.backup_archive rotate --dir /weekly --keep 4
if ($LASTEXITCODE -ne 0) { throw "Ротация еженедельных копий не выполнена" }

Write-Host "Создана зашифрованная копия database\backups\daily\$encryptedName"
