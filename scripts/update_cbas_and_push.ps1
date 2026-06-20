param(
  [string]$SourceDir = "C:\Users\vmja2\Downloads\01_投資交易_CB_選擇權\CBAS報價及發行資訊",
  [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$repoSource = Join-Path $root "data\source\cbas"

New-Item -ItemType Directory -Force -Path $repoSource | Out-Null
Copy-Item -Path (Join-Path $SourceDir "*.xlsx") -Destination $repoSource -Force

Push-Location $root
try {
  $env:CBAS_SOURCE_DIR = $repoSource
  python scripts\update_cbas.py
  python scripts\test_cbas.py

  git add data\processed\cbas_latest.json data\history\cbas dist\data\cbas-latest.js
  $status = git status --short
  if ($status) {
    git commit -m "Update weekly CBAS dashboard"
    git push origin $Branch
  } else {
    Write-Host "沒有新的 CBAS 變更需要推送。"
  }
} finally {
  Pop-Location
}
