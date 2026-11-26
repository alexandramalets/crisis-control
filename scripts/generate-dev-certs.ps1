# Генерирует учебные сертификаты TLS в deploy\certs.
# Запуск из корня проекта: powershell -ExecutionPolicy Bypass -File scripts\generate-dev-certs.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}
& $python (Join-Path $root "scripts\generate_dev_certs.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
