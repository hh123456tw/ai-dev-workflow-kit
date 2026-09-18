param([switch]$InstallLaunchers, [switch]$CleanLegacy)
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Require-Command($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) { throw "Required command not found: $name" }
}

Require-Command git
Require-Command opencode

Write-Host '[0/5] Pruning old backups (keep newest 3)...'
$BackupRoot = Join-Path $env:USERPROFILE '.config\opencode'
$OldBackups = Get-ChildItem -Path $BackupRoot -Directory -Filter 'backup_*' -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -Skip 3
foreach ($old in $OldBackups) {
  Remove-Item -LiteralPath $old.FullName -Recurse -Force
  Write-Host "  pruned old backup: $($old.Name)"
}

Write-Host '[1/5] Installing/updating gstack for OpenCode...'
$GstackHome = Join-Path $env:USERPROFILE '.local\share\gstack'
if (Test-Path (Join-Path $GstackHome '.git')) {
  git -C $GstackHome pull --ff-only | Out-Host
} else {
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $GstackHome) | Out-Null
  git clone https://github.com/garrytan/gstack.git $GstackHome | Out-Host
}
# NOTE: gstack installs skills flat (no namespace). The selected toolbox is qa,
# qa-only, review, ship, cso, investigate, plan-ceo-review, design-review,
# benchmark. Namespaced entry points (/gstack-qa etc.) are deployed from this
# repo's commands/ in step [3/5]. `retro` is intentionally excluded: gstack
# defines it and this repo does not wrap it.
$bash = Get-Command bash -ErrorAction SilentlyContinue
if ($bash) {
  & $bash.Source (Join-Path $GstackHome 'setup') --host opencode
} else {
  Write-Warning 'bash not found. gstack clone is ready, but setup was skipped. Install Git Bash/WSL and run: bash ~/.local/share/gstack/setup --host opencode'
}

Write-Host '[2/5] Checking local model file...'
$LocalDir = Join-Path $RepoRoot '.local'
New-Item -ItemType Directory -Force -Path $LocalDir | Out-Null
$Models = Join-Path $LocalDir 'models.ps1'
$CreatedModels = $false
if (-not (Test-Path $Models)) {
  Copy-Item (Join-Path $RepoRoot 'scripts\models.ps1.example') $Models
  $CreatedModels = $true
  Write-Warning "Created $Models. Fill actual model IDs from OpenCode /models before launching the profile."
}
if ($CreatedModels) { throw "Edit $Models with actual OpenCode model IDs, then run setup again." }

Write-Host '[3/5] Deploying shared agents and commands...'
$OcConfig = Join-Path $env:USERPROFILE '.config\opencode'
$AgentsDir = Join-Path $OcConfig 'agents'
$CommandsDir = Join-Path $OcConfig 'commands'
New-Item -ItemType Directory -Force -Path $AgentsDir | Out-Null
New-Item -ItemType Directory -Force -Path $CommandsDir | Out-Null
Copy-Item (Join-Path $RepoRoot 'agents\*.md') $AgentsDir -Force
Copy-Item (Join-Path $RepoRoot 'commands\*.md') $CommandsDir -Force
$RequiredAgents = @('stable-lead.md', 'explorer.md', 'implementer.md', 'reviewer.md', 'test-writer.md')
foreach ($agent in $RequiredAgents) {
  if (-not (Test-Path (Join-Path $AgentsDir $agent))) { throw "Agent was not deployed: $agent" }
}
if (-not (Test-Path (Join-Path $CommandsDir 'stable.md'))) { throw 'Command was not deployed: stable.md' }
Write-Host '  deployed stable-lead, DeepSeek workers (explorer/implementer/reviewer/test-writer), /stable, /gstack-* commands.'
Write-Host '  The profile resolves stable-lead from this global agents directory; run setup before launching oc-product.'

Write-Host '[4/5] Deploying portable global config and gstack routing...'
$OcConfigRoot = Join-Path $env:USERPROFILE '.config\opencode'
$GlobalConfig = Join-Path $OcConfigRoot 'opencode.jsonc'
if (-not (Test-Path $GlobalConfig)) {
  Copy-Item (Join-Path $RepoRoot 'global\opencode.jsonc') $GlobalConfig
  Write-Host '  installed global opencode.jsonc (was missing).'
} else {
  $raw = Get-Content -Raw -LiteralPath $GlobalConfig
  Write-Warning "  global opencode.jsonc exists; left untouched (file: $GlobalConfig)."
  if ($raw -match 'opencode-ensemble') {
    Write-Warning '  It still references @hueyexe/opencode-ensemble. The multi-agent layer is retired; remove that plugin entry by hand.'
  }
}
$GstackConfig = Join-Path $OcConfigRoot 'gstack.jsonc'
if (-not (Test-Path $GstackConfig)) {
  Copy-Item (Join-Path $RepoRoot 'gstack\gstack.jsonc') $GstackConfig
  Write-Host '  installed gstack.jsonc (was missing).'
} else {
  Write-Host '  gstack.jsonc exists; left untouched (diff against repo gstack/ if drifted).'
}

Write-Host '[5/5] Launchers and legacy cleanup...'
if ($InstallLaunchers) {
  $Bin = Join-Path $env:USERPROFILE 'bin'
  New-Item -ItemType Directory -Force -Path $Bin | Out-Null
  $product = "@echo off`r`npowershell -NoProfile -ExecutionPolicy Bypass -File `"$RepoRoot\scripts\oc-product.ps1`" %*`r`n"
  Set-Content -Path (Join-Path $Bin 'oc-product.cmd') -Value $product -Encoding ASCII

  $userPath = [Environment]::GetEnvironmentVariable('Path','User')
  if (($userPath -split ';') -notcontains $Bin) {
    [Environment]::SetEnvironmentVariable('Path', (($userPath.TrimEnd(';') + ';' + $Bin).Trim(';')), 'User')
    Write-Warning "Added $Bin to user PATH. Open a new terminal before using oc-product."
  }
}

$LegacyFiles = @(
  (Join-Path $OcConfig 'agents\team-lead.md'),
  (Join-Path $OcConfig 'agents\team-scout.md'),
  (Join-Path $OcConfig 'agents\team-builder.md'),
  (Join-Path $OcConfig 'agents\team-reviewer.md'),
  (Join-Path $OcConfig 'commands\team.md'),
  (Join-Path $OcConfig 'ensemble.json'),
  (Join-Path $OcConfig 'profiles\team.json'),
  (Join-Path $OcConfig 'profiles\team')
)
$Present = $LegacyFiles | Where-Object { Test-Path -LiteralPath $_ }
if ($Present.Count -eq 0) {
  Write-Host '  no retired multi-agent artifacts found.'
} elseif ($CleanLegacy) {
  foreach ($item in $Present) {
    Remove-Item -LiteralPath $item -Recurse -Force
    Write-Host "  removed retired artifact: $item"
  }
} else {
  Write-Warning '  retired multi-agent artifacts still present. Re-run with -CleanLegacy to remove them:'
  foreach ($item in $Present) { Write-Host "    $item" }
}

Write-Host ''
Write-Host 'Restore complete.'
Write-Host 'Superpowers installs from the profile plugin declaration on first OpenCode launch.'
Write-Host 'Next: edit .local/models.ps1 with actual model IDs, authenticate providers locally, then run oc-product.'
