# Создаёт .env из .env.example и заполняет пустые секреты случайными значениями.
# Запуск из корня проекта: powershell -ExecutionPolicy Bypass -File scripts\init-env.ps1 [-Force]
param([switch]$Force)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$example = Join-Path $root ".env.example"
$target = Join-Path $root ".env"
$secretNames = @(
    "POSTGRES_ADMIN_PASSWORD", "DB_PASSWORD", "ANALYTICS_SERVICE_KEY",
    "JWT_SECRET_KEY", "DATASET_ENCRYPTION_KEY", "BACKUP_ENCRYPTION_KEY"
)

if ((Test-Path $target) -and -not $Force) {
    Write-Host "Файл .env уже существует. Для перезаписи запустите скрипт с параметром -Force."
    exit 0
}

function New-Secret {
    $bytes = New-Object byte[] 48
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

$lines = Get-Content -Path $example -Encoding UTF8 | ForEach-Object {
    $name = ($_ -split "=", 2)[0]
    if ($secretNames -contains $name -and $_ -match "=\s*$") { "$name=$(New-Secret)" } else { $_ }
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($target, $lines, $utf8NoBom)
Write-Host "Создан файл $target; секреты сгенерированы."
