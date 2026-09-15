param([switch]$InstallLaunchers)
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Require-Command($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) { throw "Required command not found: $name" }
}

Require-Command git
Require-Command opencode

Write-Host '[1/7] Preparing TEAM Matt skills...'
$TeamSkills = Join-Path $RepoRoot 'profiles\team\skills'
New-Item -ItemType Directory -Force -Path $TeamSkills | Out-Null
$Temp = Join-Path $env:TEMP ("mattpocock-skills-" + [guid]::NewGuid().ToString('N'))
try {
  git clone --depth 1 https://github.com/mattpocock/skills.git $Temp | Out-Host
  $wanted = @(
    'setup-matt-pocock-skills','grill-with-docs','grill-me','wayfinder','to-spec','to-tickets',
    'implement','tdd','codebase-design','domain-modeling','diagnosing-bugs','code-review',
    'research','resolving-merge-conflicts','handoff'
  )
  foreach ($name in $wanted) {
    $match = Get-ChildItem -Path (Join-Path $Temp 'skills') -Directory -Recurse | Where-Object { $_.Name -eq $name -and (Test-Path (Join-Path $_.FullName 'SKILL.md')) } | Select-Object -First 1
    if (-not $match) { Write-Warning "Matt skill not found upstream: $name"; continue }
    $dest = Join-Path $TeamSkills $name
    if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
    Copy-Item $match.FullName $dest -Recurse
    Write-Host "  installed Matt skill: $name"
  }
} finally {
  if (Test-Path $Temp) { Remove-Item $Temp -Recurse -Force }
}

Write-Host '[2/7] Installing/updating gstack for OpenCode...'
$GstackHome = Join-Path $env:USERPROFILE '.local\share\gstack'
if (Test-Path (Join-Path $GstackHome '.git')) {
  git -C $GstackHome pull --ff-only | Out-Host
} else {
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $GstackHome) | Out-Null
  git clone https://github.com/garrytan/gstack.git $GstackHome | Out-Host
}
# NOTE: gstack installs skills flat (no namespace). The selected toolbox used by
# STABLE/TEAM modes is qa, qa-only, review, ship, cso, investigate,
# plan-ceo-review, design-review, benchmark. Namespaced entry points
# (/gstack-qa etc.) are deployed from this repo's commands/ in step [5/6].
# `retro` is intentionally excluded: Matt and gstack both define it.
$bash = Get-Command bash -ErrorAction SilentlyContinue
if ($bash) {
  & $bash.Source (Join-Path $GstackHome 'setup') --host opencode
} else {
  Write-Warning 'bash not found. gstack clone is ready, but setup was skipped. Install Git Bash/WSL and run: bash ~/.local/share/gstack/setup --host opencode'
}

Write-Host '[3/7] Checking local model file...'
$LocalDir = Join-Path $RepoRoot '.local'
New-Item -ItemType Directory -Force -Path $LocalDir | Out-Null
$Models = Join-Path $LocalDir 'models.ps1'
$CreatedModels = $false
if (-not (Test-Path $Models)) {
  Copy-Item (Join-Path $RepoRoot 'scripts\models.ps1.example') $Models
  $CreatedModels = $true
  Write-Warning "Created $Models. Fill actual model IDs from OpenCode /models before launching profiles."
}
if ($CreatedModels) { throw "Edit $Models with actual OpenCode model IDs, then run setup again." }

Write-Host '[4/7] Installing TEAM Ensemble configuration...'
$EnsembleTemplate = Join-Path $RepoRoot 'profiles\team\ensemble.json.template'
$EnsembleDir = Join-Path $env:USERPROFILE '.config\opencode'
$EnsembleConfig = Join-Path $EnsembleDir 'ensemble.json'
New-Item -ItemType Directory -Force -Path $EnsembleDir | Out-Null
(Get-Content -Raw $EnsembleTemplate).Replace('__OPENCODE_WORKER_MODEL__', $env:OPENCODE_WORKER_MODEL) | Set-Content -Path $EnsembleConfig -Encoding UTF8
Write-Host "  installed $EnsembleConfig for $($env:OPENCODE_WORKER_MODEL)"

Write-Host '[5/7] Deploying shared agents and commands...'
$OcConfig = Join-Path $env:USERPROFILE '.config\opencode'
$AgentsDir = Join-Path $OcConfig 'agents'
$CommandsDir = Join-Path $OcConfig 'commands'
New-Item -ItemType Directory -Force -Path $AgentsDir | Out-Null
New-Item -ItemType Directory -Force -Path $CommandsDir | Out-Null
Copy-Item (Join-Path $RepoRoot 'agents\*.md') $AgentsDir -Force
Copy-Item (Join-Path $RepoRoot 'commands\*.md') $CommandsDir -Force
Write-Host '  deployed stable-lead, team-lead, DeepSeek workers, /stable, /team, /gstack-* commands.'
Write-Host '  NOTE: repo reviewer.md (DeepSeek) deploys to global agents/; the TEAM profile keeps its own GPT reviewer.'

Write-Host '[6/7] Deploying portable global config and gstack routing...'
$OcConfigRoot = Join-Path $env:USERPROFILE '.config\opencode'
$GlobalConfig = Join-Path $OcConfigRoot 'opencode.jsonc'
if (-not (Test-Path $GlobalConfig)) {
  Copy-Item (Join-Path $RepoRoot 'global\opencode.jsonc') $GlobalConfig
  Write-Host '  installed global opencode.jsonc (was missing).'
} else {
  Write-Host '  global opencode.jsonc exists; left untouched (diff against repo global/ if drifted).'
}
$GstackConfig = Join-Path $OcConfigRoot 'gstack.jsonc'
if (-not (Test-Path $GstackConfig)) {
  Copy-Item (Join-Path $RepoRoot 'gstack\gstack.jsonc') $GstackConfig
  Write-Host '  installed gstack.jsonc (was missing).'
} else {
  Write-Host '  gstack.jsonc exists; left untouched (diff against repo gstack/ if drifted).'
}

Write-Host '[7/7] Launchers...'
if ($InstallLaunchers) {
  $Bin = Join-Path $env:USERPROFILE 'bin'
  New-Item -ItemType Directory -Force -Path $Bin | Out-Null
  $product = "@echo off`r`npowershell -NoProfile -ExecutionPolicy Bypass -File `"$RepoRoot\scripts\oc-product.ps1`" %*`r`n"
  $team = "@echo off`r`npowershell -NoProfile -ExecutionPolicy Bypass -File `"$RepoRoot\scripts\oc-team.ps1`" %*`r`n"
  Set-Content -Path (Join-Path $Bin 'oc-product.cmd') -Value $product -Encoding ASCII
  Set-Content -Path (Join-Path $Bin 'oc-team.cmd') -Value $team -Encoding ASCII

  $userPath = [Environment]::GetEnvironmentVariable('Path','User')
  if (($userPath -split ';') -notcontains $Bin) {
    [Environment]::SetEnvironmentVariable('Path', (($userPath.TrimEnd(';') + ';' + $Bin).Trim(';')), 'User')
    Write-Warning "Added $Bin to user PATH. Open a new terminal before using oc-product/oc-team."
  }
}

Write-Host ''
Write-Host 'Restore complete.'
Write-Host 'PRODUCT Superpowers will install from the PRODUCT profile plugin declaration on first OpenCode launch.'
Write-Host 'Next: edit .local/models.ps1 with actual model IDs, authenticate providers locally, then run oc-product / oc-team.'
