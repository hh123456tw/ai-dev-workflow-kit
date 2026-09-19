# Stable mode: full Superpowers plus the cost-control lead. Safe daily default.
$ErrorActionPreference = 'Stop'
$mode = Join-Path $env:USERPROFILE '.config\opencode\modes\stable'
$config = Join-Path $mode 'opencode.jsonc'
if (-not (Test-Path -LiteralPath $config)) {
  throw "Stable mode is not deployed at $mode. Run scripts/setup-windows.ps1 first."
}
$env:OPENCODE_CONFIG = $config
Remove-Item Env:OPENCODE_CONFIG_DIR -ErrorAction SilentlyContinue
Remove-Item Env:OPENCODE_CONFIG_CONTENT -ErrorAction SilentlyContinue
& opencode @args
exit $LASTEXITCODE
