param([switch]$InstallLaunchers)
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Require-Command($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) { throw "Required command not found: $name" }
}

Require-Command git
Require-Command opencode

Write-Host '[1/4] Preparing TEAM Matt skills...'
$TeamSkills = Join-Path $RepoRoot 'profiles\team\skills'
New-Item -ItemType Directory -Force -Path $TeamSkills | Out-Null
$Temp = Join-Path $env:TEMP ("mattpocock-skills-" + [guid]::NewGuid().ToString('N'))
try {
  git clone --depth 1 https://github.com/mattpocock/skills.git $Temp | Out-Host
  $wanted = @(
    'setup-matt-pocock-skills','grill-with-docs','grill-me','wayfinder','to-spec','to-tickets',
    'tdd','codebase-design','domain-modeling','diagnosing-bugs','code-review','research','handoff'
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

Write-Host '[2/4] Installing/updating gstack for OpenCode with gstack- prefix...'
$GstackHome = Join-Path $env:USERPROFILE '.local\share\gstack'
if (Test-Path (Join-Path $GstackHome '.git')) {
  git -C $GstackHome pull --ff-only | Out-Host
} else {
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $GstackHome) | Out-Null
  git clone https://github.com/garrytan/gstack.git $GstackHome | Out-Host
}
$bash = Get-Command bash -ErrorAction SilentlyContinue
if ($bash) {
  & $bash.Source (Join-Path $GstackHome 'setup') --host opencode --prefix
} else {
  Write-Warning 'bash not found. gstack clone is ready, but setup was skipped. Install Git Bash/WSL and run: bash ~/.local/share/gstack/setup --host opencode --prefix'
}

Write-Host '[3/4] Checking local model file...'
$LocalDir = Join-Path $RepoRoot '.local'
New-Item -ItemType Directory -Force -Path $LocalDir | Out-Null
$Models = Join-Path $LocalDir 'models.ps1'
if (-not (Test-Path $Models)) {
  Copy-Item (Join-Path $RepoRoot 'scripts\models.ps1.example') $Models
  Write-Warning "Created $Models. Fill actual model IDs from OpenCode /models before launching profiles."
}

Write-Host '[4/4] Launchers...'
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
