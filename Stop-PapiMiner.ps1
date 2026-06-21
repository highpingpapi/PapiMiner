param(
    [int] $Port = 8788
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$LocalDir = Join-Path $Root "local"
$PidFile = Join-Path $LocalDir "PapiMiner-server-$Port.pid"

$Matches = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "python.exe" -and
    ($_.CommandLine -match "PapiMiner\.py" -or $_.CommandLine -match "papiminer\.py") -and
    $_.CommandLine -match "--port\s+$Port"
}

if ($Matches) {
    foreach ($Proc in $Matches) {
        Stop-Process -Id $Proc.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped PapiMiner pid $($Proc.ProcessId)."
    }
    exit 0
}

if (-not (Test-Path $PidFile)) {
    Write-Host "No PapiMiner pid file found for port $Port."
    exit 0
}

$PidText = Get-Content $PidFile -ErrorAction SilentlyContinue
if (-not $PidText) {
    Write-Host "Pid file is empty: $PidFile"
    exit 0
}

$Proc = Get-Process -Id ([int]$PidText) -ErrorAction SilentlyContinue
if ($Proc -and $Proc.ProcessName -like "python*") {
    Stop-Process -Id $Proc.Id -Force
    Write-Host "Stopped PapiMiner pid $PidText."
} else {
    Write-Host "PapiMiner process is not running."
}
