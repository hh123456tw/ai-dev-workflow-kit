# Core CodeGraph canary treatment. The normal oc-core launcher remains the control.
$ErrorActionPreference = 'Stop'
$mode = Join-Path $env:USERPROFILE '.config\opencode\modes\core'
$config = Join-Path $mode 'opencode-codegraph.jsonc'
$engine = Join-Path $env:USERPROFILE '.codegraph\bin\v0.20.1\codegraph-server-win32-x64.exe'
$onnxRuntime = Join-Path $env:USERPROFILE '.codegraph\bin\v0.20.1\onnxruntime.dll'
$expectedEngineHash = 'aa1b6108217c119af6ac444b8652a0eadcfe2c343bff78ead2edd15b6b7b15b1'
$expectedOnnxHash = '52f8ebe8f08f369a44fed6d1cb680c7c89169795e1c2949ee25b88b538ef0948'

if (-not (Test-Path -LiteralPath $config)) {
  throw "Core CodeGraph canary is not deployed at $config. Run scripts/setup-windows.ps1 first."
}
if (-not (Test-Path -LiteralPath (Join-Path $mode 'skills\test-driven-development'))) {
  throw "Core skills are missing at $mode\skills. Re-run scripts/setup-windows.ps1."
}
if (-not (Test-Path -LiteralPath $engine)) {
  throw "Pinned CodeGraph 0.20.1 is missing. Run scripts/install-codegraph-windows.ps1 first."
}
if (-not (Test-Path -LiteralPath $onnxRuntime)) {
  throw "Pinned CodeGraph onnxruntime.dll is missing. Run scripts/install-codegraph-windows.ps1 first."
}
$actualEngineHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $engine).Hash.ToLowerInvariant()
if ($actualEngineHash -ne $expectedEngineHash) {
  throw "CodeGraph binary checksum mismatch. Expected $expectedEngineHash but found $actualEngineHash."
}
$actualOnnxHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $onnxRuntime).Hash.ToLowerInvariant()
if ($actualOnnxHash -ne $expectedOnnxHash) {
  throw "CodeGraph onnxruntime.dll checksum mismatch. Expected $expectedOnnxHash but found $actualOnnxHash."
}

$env:OPENCODE_CONFIG = $config
$env:OPENCODE_CONFIG_DIR = $mode
$env:XDG_CONFIG_HOME = Join-Path $mode 'xdg'
$env:CODEGRAPH_HOME = $env:USERPROFILE.Replace('\', '/')
$env:OPENCODE_DISABLE_EXTERNAL_SKILLS = '1'
Remove-Item Env:OPENCODE_CONFIG_CONTENT -ErrorAction SilentlyContinue
Remove-Item Env:OPENCODE_DISABLE_DEFAULT_PLUGINS -ErrorAction SilentlyContinue
& opencode --pure @args
exit $LASTEXITCODE
