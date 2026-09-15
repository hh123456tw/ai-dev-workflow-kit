param([Parameter(ValueFromRemainingArguments=$true)][string[]]$OpenCodeArgs)
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Models = Join-Path $RepoRoot '.local\models.ps1'
if (-not (Test-Path $Models)) { throw "Missing $Models. Copy scripts/models.ps1.example to .local/models.ps1 and fill actual model IDs." }
. $Models
if ([string]::IsNullOrWhiteSpace($env:OPENCODE_PRIMARY_MODEL)) { throw 'OPENCODE_PRIMARY_MODEL is empty.' }
if ([string]::IsNullOrWhiteSpace($env:OPENCODE_WORKER_MODEL)) { throw 'OPENCODE_WORKER_MODEL is empty.' }
$oldConfig=$env:OPENCODE_CONFIG; $oldDir=$env:OPENCODE_CONFIG_DIR
try {
  $env:OPENCODE_CONFIG = Join-Path $RepoRoot 'profiles\product\opencode.jsonc'
  $env:OPENCODE_CONFIG_DIR = Join-Path $RepoRoot 'profiles\product'
  & opencode @OpenCodeArgs
  exit $LASTEXITCODE
} finally {
  $env:OPENCODE_CONFIG=$oldConfig; $env:OPENCODE_CONFIG_DIR=$oldDir
}
