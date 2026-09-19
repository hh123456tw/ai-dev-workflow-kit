# Launch OpenCode Desktop in Vanilla mode with its own user-data directory,
# so it can run alongside the stock Stable window.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'opencode-desktop-common.ps1')

$mode = Join-Path $env:USERPROFILE '.config\opencode\modes\vanilla'
$config = Join-Path $mode 'opencode.jsonc'
if (-not (Test-Path -LiteralPath $config)) {
  throw "Vanilla mode is not deployed at $mode. Run scripts/setup-windows.ps1 first."
}

$env:OPENCODE_CONFIG = $config
Remove-Item Env:OPENCODE_CONFIG_DIR -ErrorAction SilentlyContinue
Remove-Item Env:OPENCODE_CONFIG_CONTENT -ErrorAction SilentlyContinue

$userData = Join-Path $env:APPDATA 'ai.opencode.desktop-vanilla'
New-Item -ItemType Directory -Force -Path $userData | Out-Null

$exe = Get-OpenCodeDesktopPath
Start-Process -FilePath $exe -ArgumentList @("--user-data-dir=$userData")
