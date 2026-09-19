# Vanilla mode: full upstream Superpowers, OpenCode build agent.
$ErrorActionPreference = 'Stop'
$mode = Join-Path $env:USERPROFILE '.config\opencode\modes\vanilla'
$config = Join-Path $mode 'opencode.jsonc'
if (-not (Test-Path -LiteralPath $config)) {
  throw "Vanilla mode is not deployed at $mode. Run scripts/setup-windows.ps1 first."
}
$env:OPENCODE_CONFIG = $config
Remove-Item Env:OPENCODE_CONFIG_DIR -ErrorAction SilentlyContinue
Remove-Item Env:OPENCODE_CONFIG_CONTENT -ErrorAction SilentlyContinue
Remove-Item Env:OPENCODE_DISABLE_EXTERNAL_SKILLS -ErrorAction SilentlyContinue
Remove-Item Env:OPENCODE_DISABLE_DEFAULT_PLUGINS -ErrorAction SilentlyContinue
# Vanilla inherits the global config directory; only Core uses an isolated config root.
& opencode @args
exit $LASTEXITCODE
