# Launch OpenCode Desktop in Core mode with its own user-data directory and a
# fully isolated config root.
# Note: OpenCode Desktop 1.18.31 allows only one instance at a time, so close any
# running Desktop window before using this entry.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'opencode-desktop-common.ps1')

$mode = Join-Path $env:USERPROFILE '.config\opencode\modes\core'
$config = Join-Path $mode 'opencode.jsonc'
if (-not (Test-Path -LiteralPath $config)) {
  Fail-DesktopLaunch "Core mode is not deployed at $mode. Run scripts/setup-windows.ps1 first."
}
if (-not (Test-Path -LiteralPath (Join-Path $mode 'skills\test-driven-development'))) {
  Fail-DesktopLaunch "Core skills are missing at $mode\skills. Re-run scripts/setup-windows.ps1."
}

$exe = Get-OpenCodeDesktopPath
if (-not $exe) { Fail-DesktopLaunch 'OpenCode Desktop executable not found. Install OpenCode Desktop first.' }

$env:OPENCODE_CONFIG = $config
$env:OPENCODE_CONFIG_DIR = $mode
$env:XDG_CONFIG_HOME = Join-Path $mode 'xdg'
$env:OPENCODE_DISABLE_EXTERNAL_SKILLS = '1'
Remove-Item Env:OPENCODE_CONFIG_CONTENT -ErrorAction SilentlyContinue
# Default provider plugins are required to resolve the pinned model.
Remove-Item Env:OPENCODE_DISABLE_DEFAULT_PLUGINS -ErrorAction SilentlyContinue

$userData = Join-Path $env:APPDATA 'ai.opencode.desktop-core'
New-Item -ItemType Directory -Force -Path $userData | Out-Null

Write-DesktopLog "launching Core: $exe --user-data-dir=$userData"
Start-Process -FilePath $exe -ArgumentList @("--user-data-dir=$userData")
