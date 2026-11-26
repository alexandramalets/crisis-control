# Создаёт базу crisis_analytics в локальном PostgreSQL (порт 5432, pgAdmin)
# и копирует схему и данные из Docker. Запуск из корня проекта:
#   powershell -ExecutionPolicy Bypass -File scripts\ensure-local-postgres.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Read-DotEnv([string]$path) {
    $map = @{}
    if (-not (Test-Path $path)) { return $map }
    Get-Content -Path $path -Encoding UTF8 | ForEach-Object {
        if ($_ -match "^\s*#" -or $_ -notmatch "=") { return }
        $parts = $_ -split "=", 2
        $map[$parts[0].Trim()] = $parts[1].Trim()
    }
    return $map
}

$envMap = Read-DotEnv (Join-Path $root ".env")
$dbName = if ($envMap["DB_NAME"]) { $envMap["DB_NAME"] } else { "crisis_analytics" }
$adminUser = if ($envMap["POSTGRES_ADMIN_USER"]) { $envMap["POSTGRES_ADMIN_USER"] } else { "postgres" }
$adminPassword = if ($envMap["POSTGRES_ADMIN_PASSWORD"]) { $envMap["POSTGRES_ADMIN_PASSWORD"] } else { "admin" }
$appUser = if ($envMap["DB_USER"]) { $envMap["DB_USER"] } else { "crisis_app" }
$appPassword = if ($envMap["DB_PASSWORD"]) { $envMap["DB_PASSWORD"] } else { $adminPassword }
$pgPort = if ($envMap["HOST_PG_PORT"]) { $envMap["HOST_PG_PORT"] } else { "5432" }

$psql = @(
    "D:\PostgreSQL\17\bin\psql.exe",
    "D:\PostgreSQL\16\bin\psql.exe",
    "C:\Program Files\PostgreSQL\17\bin\psql.exe",
    "C:\Program Files\PostgreSQL\16\bin\psql.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $psql) {
    throw "Не найден psql локального PostgreSQL. Укажите путь к bin в HOST_PG_BIN."
}
$pgBin = Split-Path $psql -Parent
$pgRestore = Join-Path $pgBin "pg_restore.exe"

$env:PGPASSWORD = $adminPassword
$env:PGCLIENTENCODING = "UTF8"

function Invoke-LocalSql([string]$database, [string]$sql) {
    $tmp = Join-Path $env:TEMP "crisis-local-pg.sql"
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($tmp, $sql, $utf8)
    & $psql -h 127.0.0.1 -p $pgPort -U $adminUser -d $database -v ON_ERROR_STOP=1 -f $tmp
    if ($LASTEXITCODE -ne 0) { throw "Ошибка SQL в базе $database" }
}

Write-Host "Проверка локального PostgreSQL $adminUser@127.0.0.1:$pgPort ..."
& $psql -h 127.0.0.1 -p $pgPort -U $adminUser -d postgres -c "SELECT 1" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Не удалось войти в локальный PostgreSQL. Логин $adminUser, пароль из POSTGRES_ADMIN_PASSWORD (.env)."
}

$exists = & $psql -h 127.0.0.1 -p $pgPort -U $adminUser -d postgres -At -c "SELECT 1 FROM pg_database WHERE datname = '$dbName'"
if (-not $exists) {
    Write-Host "Создаю базу $dbName ..."
    & $psql -h 127.0.0.1 -p $pgPort -U $adminUser -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $dbName"
    if ($LASTEXITCODE -ne 0) { throw "Не удалось создать базу $dbName" }
} else {
    Write-Host "База $dbName уже есть, обновляю схему и данные."
}

Invoke-LocalSql "postgres" @"
DO `$`$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$appUser') THEN
        CREATE ROLE $appUser LOGIN PASSWORD '$appPassword' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    ELSE
        ALTER ROLE $appUser WITH LOGIN PASSWORD '$appPassword';
    END IF;
END
`$`$;
GRANT CONNECT, TEMPORARY ON DATABASE $dbName TO $appUser;
"@

Write-Host "Копирование схемы из Docker..."
docker compose exec -T database pg_dump -U postgres -Fc -d $dbName -f /tmp/crisis_analytics.dump
if ($LASTEXITCODE -ne 0) { throw "pg_dump в контейнере database не выполнен. Запустите docker compose up -d database." }

$dump = Join-Path $env:TEMP "crisis_analytics.dump"
docker cp "crisis-analytics-database-1:/tmp/crisis_analytics.dump" $dump
& $pgRestore -h 127.0.0.1 -p $pgPort -U $adminUser -d $dbName --no-owner --no-acl --clean --if-exists $dump
# pg_restore может вернуть 1 из-за предупреждений; проверяем таблицы отдельно.

Invoke-LocalSql $dbName @"
GRANT USAGE, CREATE ON SCHEMA public TO $appUser;
GRANT ALL ON ALL TABLES IN SCHEMA public TO $appUser;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO $appUser;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $appUser;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $appUser;
"@

$count = & $psql -h 127.0.0.1 -p $pgPort -U $adminUser -d $dbName -At -c "SELECT count(*) FROM pg_tables WHERE schemaname = 'public';"
Write-Host "Готово. База $dbName в pgAdmin (127.0.0.1:$pgPort), таблиц: $count"
Write-Host "Обновите в pgAdmin: Databases -> $dbName -> Schemas -> public -> Tables"
