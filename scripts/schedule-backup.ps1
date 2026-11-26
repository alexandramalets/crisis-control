# Регистрирует ежедневный запуск scripts\backup.ps1 в Планировщике заданий Windows.
# Нужны права на создание задания текущему пользователю. Задание не создаётся этим файлом само при установке проекта.
param([string]$At = "02:00")
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "scripts\backup.ps1"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`""
$trigger = New-ScheduledTaskTrigger -Daily -At $At
Register-ScheduledTask -TaskName "CrisisAnalyticsBackup" -Action $action -Trigger $trigger -Description "Зашифрованная резервная копия PostgreSQL «Кризисная аналитика»" -Force | Out-Null
Write-Host "Задание CrisisAnalyticsBackup зарегистрировано, ежедневно в $At."
