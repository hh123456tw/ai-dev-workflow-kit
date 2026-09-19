# Launch OpenCode Desktop in Core mode with its own user-data directory and a
# fully isolated config root, so it can run alongside Stable and Vanilla.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'opencode-desktop-common.ps1')

$mode = Join-Path $env:USERPROFILE '.config\opencode\modes\core'
$config = Join-Path $mode 'opencode.jsonc'
if (-not (Test-Path -LiteralPath $config)) {
  throw "Core mode is not deployed at $mode. Run scripts/setup-windows.ps1 first."
}
if (-not (Test-Path -LiteralPath (Join-Path $mode 'skills\test-driven-development'))) {
  throw "Core skills are missing at $mode\skills. Re-run scripts/setup-windows.ps1."
}

$env:OPENCODE_CONFIG = $config
$env:OPENCODE_CONFIG_DIR = $mode
$env:XDG_CONFIG_HOME = Join-Path $mode 'xdg'
$env:OPENCODE_DISABLE_EXTERNAL_SKILLS = '1'
$env:OPENCODE_DISABLE_DEFAULT_PLUGINS = '1'
Remove-Item Env:OPENCODE_CONFIG_CONTENT -ErrorAction SilentlyContinue

$userData = Join-Path $env:APPDATA 'ai.opencode.desktop-core'
New-Item -ItemType Directory -Force -Path $userData | Out-Null

$exe = Get-OpenCodeDesktopPath
Start-Process -FilePath $exe -ArgumentList @("--user-data-dir=$userData")
