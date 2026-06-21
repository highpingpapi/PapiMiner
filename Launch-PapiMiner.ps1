param(
    [int] $Port = 8788,
    [switch] $Restart,
    [switch] $Open
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$LocalDir = Join-Path $Root "local"
$PidFile = Join-Path $LocalDir "PapiMiner-server-$Port.pid"
$OutLog = Join-Path $LocalDir "PapiMiner-server-$Port.out.log"
$ErrLog = Join-Path $LocalDir "PapiMiner-server-$Port.err.log"
function Test-Url {
    param([string] $Url)
    try {
        Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Get-ListeningPid {
    $line = netstat -ano | Select-String "127\.0\.0\.1:$Port\s+.*LISTENING" | Select-Object -First 1
    if ($line -and $line.Line -match "\s+(\d+)\s*$") {
        return $Matches[1]
    }
    return ""
}

function Stop-OldServer {
    $matches = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq "python.exe" -and
        ($_.CommandLine -match "PapiMiner\.py" -or $_.CommandLine -match "papiminer\.py") -and
        $_.CommandLine -match "--port\s+$Port"
    }
    foreach ($proc in $matches) {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    }
    if (-not (Test-Path $PidFile)) {
        return
    }
    $oldPid = Get-Content $PidFile -ErrorAction SilentlyContinue
    if (-not $oldPid) {
        return
    }
    $proc = Get-Process -Id ([int]$oldPid) -ErrorAction SilentlyContinue
    if ($proc -and $proc.ProcessName -like "python*") {
        Stop-Process -Id $proc.Id -Force
    }
    Start-Sleep -Milliseconds 500
    $listeningPid = Get-ListeningPid
    if ($listeningPid) {
        $listener = Get-Process -Id ([int]$listeningPid) -ErrorAction SilentlyContinue
        if ($listener -and $listener.ProcessName -like "python*") {
            Stop-Process -Id $listener.Id -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 500
        }
    }
}

New-Item -ItemType Directory -Force -Path $LocalDir | Out-Null
$Url = "http://127.0.0.1:$Port/"

if ($Restart) {
    Stop-OldServer
}

if (Test-Url "$Url/api/ready") {
    $ListeningPid = Get-ListeningPid
    if ($ListeningPid) {
        Set-Content -Path $PidFile -Value $ListeningPid -Encoding ASCII
    }
    if ($Open) {
        Start-Process $Url
    }
    Write-Host "PapiMiner is already running: $Url"
    exit 0
}

$Python = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $Python) {
    Write-Error "Python was not found in PATH. Install Python or start PapiMiner from an environment that has python."
    exit 1
}

$Args = @(
    (Join-Path $Root "PapiMiner.py"),
    "serve",
    "--host", "127.0.0.1",
    "--port", "$Port"
)

$Process = Start-Process `
    -FilePath $Python.Source `
    -ArgumentList $Args `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $OutLog `
    -RedirectStandardError $ErrLog `
    -PassThru

Set-Content -Path $PidFile -Value $Process.Id -Encoding ASCII

$Ready = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 500
    if (Test-Url "$Url/api/ready") {
        $Ready = $true
        break
    }
}

if (-not $Ready) {
    Write-Error "PapiMiner did not become ready. Check: $ErrLog"
    exit 1
}

$ListeningPid = Get-ListeningPid
if ($ListeningPid) {
    Set-Content -Path $PidFile -Value $ListeningPid -Encoding ASCII
}

Write-Host "PapiMiner started: $Url"
if ($Open) {
    Start-Process $Url
    Write-Host "Opened in the system browser because -Open was provided."
} else {
    Write-Host "Use the Codex in-app browser or open this URL manually."
}
Write-Host "Mode: plain-only"
