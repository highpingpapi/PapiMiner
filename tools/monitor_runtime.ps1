param(
  [string]$Title = "PapiMiner Monitor",
  [string]$LogPath = "",
  [string]$ApiBase = "",
  [int]$IntervalSec = 2
)

$ErrorActionPreference = "SilentlyContinue"
$Host.UI.RawUI.WindowTitle = $Title
if ($IntervalSec -lt 1) { $IntervalSec = 1 }

function Show-GpuTable {
  Write-Host "GPU sensors / 显卡传感器" -ForegroundColor Cyan
  $query = "index,name,temperature.gpu,power.draw,power.limit,utilization.gpu,clocks.sm,clocks.mem,fan.speed,memory.used,memory.total"
  $rows = & nvidia-smi "--query-gpu=$query" "--format=csv,noheader,nounits" 2>$null
  if (-not $rows) {
    Write-Host "nvidia-smi not available or no NVIDIA GPU detected." -ForegroundColor Yellow
    return
  }
  foreach ($row in $rows) {
    $cols = $row -split ",\s*"
    if ($cols.Count -lt 11) {
      Write-Host $row
      continue
    }
    $line = "GPU {0} | {1} | {2} C | {3}/{4} W | util {5}% | core {6} MHz | mem {7} MHz | fan {8}% | VRAM {9}/{10} MiB" -f `
      $cols[0], $cols[1], $cols[2], $cols[3], $cols[4], $cols[5], $cols[6], $cols[7], $cols[8], $cols[9], $cols[10]
    Write-Host $line
  }
}

function Show-GpuProcesses {
  Write-Host ""
  Write-Host "GPU processes / 显卡进程" -ForegroundColor Cyan
  $pmon = & nvidia-smi pmon -c 1 2>$null
  if ($pmon) {
    $pmon | Select-Object -First 20 | ForEach-Object { Write-Host $_ }
  } else {
    Write-Host "No process data."
  }
}

function Show-Metrics {
  if (-not $ApiBase) { return }
  Write-Host ""
  Write-Host "Useful metrics / useful-work 指标" -ForegroundColor Cyan
  try {
    $metrics = Invoke-WebRequest -UseBasicParsing -Uri "$($ApiBase.TrimEnd('/'))/metrics" -TimeoutSec 1
    $lines = $metrics.Content -split "`n" |
      Where-Object {
        $_ -match "akoya|useful|share|gemm|launch|hash|layer|vllm" -and
        $_ -notmatch "^#"
      } |
      Select-Object -First 24
    if ($lines) {
      $lines | ForEach-Object { Write-Host $_ }
    } else {
      Write-Host "Metrics endpoint is reachable, but no selected mining metrics were found."
    }
  } catch {
    Write-Host "Metrics unavailable at $ApiBase." -ForegroundColor Yellow
  }
}

function Show-LogTail {
  if (-not $LogPath) { return }
  Write-Host ""
  Write-Host "Recent log / 最近日志" -ForegroundColor Cyan
  if (Test-Path -LiteralPath $LogPath) {
    Get-Content -LiteralPath $LogPath -Tail 28 -Encoding UTF8
  } else {
    Write-Host "Log file not found yet: $LogPath" -ForegroundColor Yellow
  }
}

while ($true) {
  Clear-Host
  Write-Host $Title -ForegroundColor Green
  Write-Host ("Updated / 更新时间: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
  Write-Host "Close this window or press Ctrl+C to stop the monitor. It does not stop the miner."
  Write-Host ""
  Show-GpuTable
  Show-GpuProcesses
  Show-Metrics
  Show-LogTail
  Start-Sleep -Seconds $IntervalSec
}
