# Launch OpenCode Desktop in Vanilla mode with its own user-data directory.
# Note: OpenCode Desktop 1.18.31 allows only one instance at a time, so close any
# running Desktop window before using this entry.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'opencode-desktop-common.ps1')

$mode = Join-Path $env:USERPROFILE '.config\opencode\modes\vanilla'
$config = Join-Path $mode 'opencode.jsonc'
if (-not (Test-Path -LiteralPath $config)) {
  Fail-DesktopLaunch "Vanilla mode is not deployed at $mode. Run scripts/setup-windows.ps1 first."
}

$exe = Get-OpenCodeDesktopPath
if (-not $exe) { Fail-DesktopLaunch 'OpenCode Desktop executable not found. Install OpenCode Desktop first.' }

$env:OPENCODE_CONFIG = $config
Remove-Item Env:OPENCODE_CONFIG_DIR -ErrorAction SilentlyContinue
Remove-Item Env:OPENCODE_CONFIG_CONTENT -ErrorAction SilentlyContinue
Remove-Item Env:OPENCODE_DISABLE_EXTERNAL_SKILLS -ErrorAction SilentlyContinue
Remove-Item Env:OPENCODE_DISABLE_DEFAULT_PLUGINS -ErrorAction SilentlyContinue
# Vanilla inherits the global config directory; only Core uses an isolated config root.

$userData = Join-Path $env:APPDATA 'ai.opencode.desktop-vanilla'
New-Item -ItemType Directory -Force -Path $userData | Out-Null

Write-DesktopLog "launching Vanilla: $exe --user-data-dir=$userData"
Start-Process -FilePath $exe -ArgumentList @("--user-data-dir=$userData")
