param([switch]$CleanLegacy)
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Require-Command($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) { throw "Required command not found: $name" }
}

$CoreSkills = @(
  'test-driven-development',
  'systematic-debugging',
  'verification-before-completion',
  'requesting-code-review',
  'receiving-code-review',
  'finishing-a-development-branch'
)
$RequiredSuperpowersVersion = '6.3.0'

function Get-SuperpowersPackage {
  $root = Join-Path $env:USERPROFILE '.cache\opencode\packages'
  if (-not (Test-Path -LiteralPath $root)) { return $null }
  # The cache nests by source path, for example
  # packages/superpowers@git+https_/github.com/obra/superpowers.git/node_modules/superpowers
  $candidates = Get-ChildItem -LiteralPath $root -Directory -Recurse -Depth 6 -Filter 'superpowers' -ErrorAction SilentlyContinue |
    Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'package.json') } |
    Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'skills') }
  $best = $null
  $bestVersion = $null
  foreach ($candidate in $candidates) {
    $version = (Get-Content (Join-Path $candidate.FullName 'package.json') -Raw | ConvertFrom-Json).version
    if ($version -eq $RequiredSuperpowersVersion) { return $candidate.FullName }
    if ($null -eq $bestVersion -or [version]$version -gt [version]$bestVersion) {
      $best = $candidate.FullName
      $bestVersion = $version
    }
  }
  # No pinned match: return the newest so the version check can report it clearly.
  return $best
}

function Get-WorkingBash {
  $candidates = @(
    (Join-Path $env:PROGRAMFILES 'Git\bin\bash.exe'),
    (Join-Path ${env:ProgramFiles(x86)} 'Git\bin\bash.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Git\bin\bash.exe')
  )
  $command = Get-Command bash -ErrorAction SilentlyContinue
  if ($command) { $candidates += $command.Source }
  foreach ($candidate in $candidates) {
    if (-not (Test-Path -LiteralPath $candidate)) { continue }
    try {
      $probe = & $candidate -c 'echo BASH_OK' 2>$null
      if ($probe -match 'BASH_OK') { return $candidate }
    } catch { }
  }
  return $null
}

Require-Command git
Require-Command opencode

$OcConfig = Join-Path $env:USERPROFILE '.config\opencode'
$ModesDir = Join-Path $OcConfig 'modes'

Write-Host '[0/6] Backing up managed configuration...'
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$Backup = Join-Path $OcConfig "backup_$Stamp"
New-Item -ItemType Directory -Force -Path $Backup | Out-Null
foreach ($item in @('opencode.jsonc', 'agents', 'commands')) {
  $source = Join-Path $OcConfig $item
  if (Test-Path -LiteralPath $source) { Copy-Item -LiteralPath $source -Destination (Join-Path $Backup $item) -Recurse -Force }
}
# Mode configs are backed up, but the regenerated skill copies and the isolated XDG
# root are not, to keep backups small.
$modesSource = Join-Path $OcConfig 'modes'
if (Test-Path -LiteralPath $modesSource) {
  $modesTarget = Join-Path $Backup 'modes'
  New-Item -ItemType Directory -Force -Path $modesTarget | Out-Null
  Copy-Item -LiteralPath (Join-Path $modesSource '*.ps1') $modesTarget -Force -ErrorAction SilentlyContinue
  foreach ($mode in @('vanilla', 'stable')) {
    $source = Join-Path $modesSource $mode
    if (Test-Path -LiteralPath $source) { Copy-Item -LiteralPath $source -Destination (Join-Path $modesTarget $mode) -Recurse -Force }
  }
  $coreSource = Join-Path $modesSource 'core'
  if (Test-Path -LiteralPath $coreSource) {
    $coreTarget = Join-Path $modesTarget 'core'
    New-Item -ItemType Directory -Force -Path $coreTarget | Out-Null
    foreach ($item in @('opencode.jsonc', 'agents')) {
      $source = Join-Path $coreSource $item
      if (Test-Path -LiteralPath $source) { Copy-Item -LiteralPath $source -Destination (Join-Path $coreTarget $item) -Recurse -Force }
    }
  }
}
# CLI shims and the two mode shortcuts this repository owns.
$binSource = Join-Path $env:USERPROFILE 'bin'
if (Test-Path -LiteralPath $binSource) {
  $binTarget = Join-Path $Backup 'bin'
  New-Item -ItemType Directory -Force -Path $binTarget | Out-Null
  Copy-Item -LiteralPath (Join-Path $binSource 'oc-*.cmd') $binTarget -Force -ErrorAction SilentlyContinue
}
foreach ($desktop in @((Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'), [Environment]::GetFolderPath('Desktop'))) {
  foreach ($label in @('OpenCode Vanilla', 'OpenCode Core')) {
    $source = Join-Path $desktop "$label.lnk"
    if (Test-Path -LiteralPath $source) { Copy-Item -LiteralPath $source $Backup -Force }
  }
}
Get-ChildItem -Path $OcConfig -Directory -Filter 'backup_*' | Sort-Object Name -Descending | Select-Object -Skip 3 | ForEach-Object {
  Remove-Item -LiteralPath $_.FullName -Recurse -Force
}
Write-Host "  backup written to $Backup"

Write-Host '[1/6] Installing/updating gstack for OpenCode...'
$GstackHome = Join-Path $env:USERPROFILE '.local\share\gstack'
if (Test-Path (Join-Path $GstackHome '.git')) {
  git -C $GstackHome pull --ff-only | Out-Host
} else {
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $GstackHome) | Out-Null
  git clone https://github.com/garrytan/gstack.git $GstackHome | Out-Host
}
$bash = Get-WorkingBash
if ($bash) {
  & $bash (Join-Path $GstackHome 'setup') --host opencode
} else {
  Write-Warning 'No working bash found. The gstack clone is ready, but setup was skipped. Install Git Bash or WSL and run: bash ~/.local/share/gstack/setup --host opencode'
}

Write-Host '[2/6] Deploying shared global agents and commands...'
$AgentsDir = Join-Path $OcConfig 'agents'
$CommandsDir = Join-Path $OcConfig 'commands'
New-Item -ItemType Directory -Force -Path $AgentsDir | Out-Null
New-Item -ItemType Directory -Force -Path $CommandsDir | Out-Null
Copy-Item (Join-Path $RepoRoot 'agents\*.md') $AgentsDir -Force
Copy-Item (Join-Path $RepoRoot 'commands\*.md') $CommandsDir -Force
foreach ($agent in @('stable-lead.md', 'explorer.md', 'implementer.md', 'reviewer.md', 'test-writer.md')) {
  if (-not (Test-Path (Join-Path $AgentsDir $agent))) { throw "Agent was not deployed: $agent" }
}
if (-not (Test-Path (Join-Path $CommandsDir 'stable.md'))) { throw 'Command was not deployed: stable.md' }
Write-Host '  deployed stable-lead, DeepSeek workers, /stable, /gstack-* commands.'

Write-Host '[3/6] Deploying the three isolated mode configs and the portable global config...'
New-Item -ItemType Directory -Force -Path $ModesDir | Out-Null
foreach ($mode in @('vanilla', 'stable')) {
  $target = Join-Path $ModesDir $mode
  New-Item -ItemType Directory -Force -Path $target | Out-Null
  Copy-Item (Join-Path $RepoRoot "modes\$mode\opencode.jsonc") (Join-Path $target 'opencode.jsonc') -Force
}
$CoreDir = Join-Path $ModesDir 'core'
New-Item -ItemType Directory -Force -Path (Join-Path $CoreDir 'agents') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $CoreDir 'xdg') | Out-Null
Copy-Item (Join-Path $RepoRoot 'modes\core\opencode.jsonc') (Join-Path $CoreDir 'opencode.jsonc') -Force
Copy-Item (Join-Path $RepoRoot 'modes\core\agents\core-lead.md') (Join-Path $CoreDir 'agents') -Force
foreach ($worker in @('explorer.md', 'implementer.md', 'reviewer.md', 'test-writer.md')) {
  Copy-Item (Join-Path $RepoRoot "agents\$worker") (Join-Path $CoreDir 'agents') -Force
}
foreach ($script in @('opencode-desktop-common.ps1', 'desktop-vanilla.ps1', 'desktop-core.ps1', 'oc-vanilla.ps1', 'oc-stable.ps1', 'oc-core.ps1')) {
  Copy-Item (Join-Path $RepoRoot "scripts\$script") (Join-Path $ModesDir $script) -Force
}
Write-Host "  deployed vanilla, stable, core, and mode launchers under $ModesDir."

# The stock OpenCode shortcut and the stock global config are Stable. Install the
# portable global config only when none exists; never overwrite the user's own.
$GlobalConfig = Join-Path $OcConfig 'opencode.jsonc'
if (-not (Test-Path -LiteralPath $GlobalConfig)) {
  Copy-Item (Join-Path $RepoRoot 'global\opencode.jsonc') $GlobalConfig
  Write-Host '  installed global opencode.jsonc (was missing), so the stock shortcut runs Stable.'
} else {
  $globalRaw = Get-Content -Raw -LiteralPath $GlobalConfig
  Write-Warning "  global opencode.jsonc exists; left untouched (file: $GlobalConfig)."
  if ($globalRaw -notmatch 'superpowers') {
    Write-Warning '  It does not load the Superpowers plugin. Stable and Vanilla will have no Superpowers skills. Add the plugin entry by hand.'
  }
  if ($globalRaw -notmatch '"default_agent"') {
    Write-Warning '  It sets no default_agent. Add "default_agent": "stable-lead" so the stock shortcut runs Stable.'
  }
  if ($globalRaw -match 'opencode-ensemble') {
    Write-Warning '  It still references @hueyexe/opencode-ensemble. The multi-agent layer is retired; remove that plugin entry by hand.'
  }
}
$GstackConfig = Join-Path $OcConfig 'gstack.jsonc'
if (-not (Test-Path -LiteralPath $GstackConfig)) {
  Copy-Item (Join-Path $RepoRoot 'gstack\gstack.jsonc') $GstackConfig
  Write-Host '  installed gstack.jsonc (was missing).'
} else {
  Write-Host '  gstack.jsonc exists; left untouched (diff against repo gstack/ if drifted).'
}

Write-Host '[4/6] Deploying Core skills from the installed Superpowers package...'
$superpowers = Get-SuperpowersPackage
if (-not $superpowers) {
  throw 'Superpowers package not found under ~/.cache/opencode/packages. Launch OpenCode once in Stable so the plugin installs, then re-run setup.'
}
$version = (Get-Content (Join-Path $superpowers 'package.json') -Raw | ConvertFrom-Json).version
if ($version -ne $RequiredSuperpowersVersion) {
  throw "Superpowers $version found but $RequiredSuperpowersVersion is required. Update the repository pin and the Core skill list deliberately before continuing."
}
$CoreSkillsDir = Join-Path $CoreDir 'skills'
if (Test-Path -LiteralPath $CoreSkillsDir) { Remove-Item -LiteralPath $CoreSkillsDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $CoreSkillsDir | Out-Null
foreach ($skill in $CoreSkills) {
  $source = Join-Path $superpowers "skills\$skill"
  if (-not (Test-Path -LiteralPath $source)) { throw "Core skill missing from Superpowers package: $skill" }
  Copy-Item -LiteralPath $source -Destination (Join-Path $CoreSkillsDir $skill) -Recurse -Force
}
[ordered]@{
  superpowers_version = $version
  skills = $CoreSkills
  deployed_at = (Get-Date).ToString('o')
} | ConvertTo-Json -Depth 4 | Set-Content -Path (Join-Path $CoreSkillsDir 'manifest.json') -Encoding UTF8
Write-Host "  deployed $($CoreSkills.Count) Core skills from Superpowers $version."

Write-Host '[5/6] Installing CLI launchers...'
$Bin = Join-Path $env:USERPROFILE 'bin'
New-Item -ItemType Directory -Force -Path $Bin | Out-Null
foreach ($mode in @('vanilla', 'stable', 'core')) {
  $content = "@echo off`r`npowershell -NoProfile -ExecutionPolicy Bypass -File `"$ModesDir\oc-$mode.ps1`" %*`r`n"
  Set-Content -Path (Join-Path $Bin "oc-$mode.cmd") -Value $content -Encoding ASCII
}
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if (($userPath -split ';') -notcontains $Bin) {
  [Environment]::SetEnvironmentVariable('Path', (($userPath.TrimEnd(';') + ';' + $Bin).Trim(';')), 'User')
  Write-Warning "Added $Bin to user PATH. Open a new terminal before using oc-vanilla, oc-stable, or oc-core."
}
Write-Host '  installed oc-vanilla, oc-stable, oc-core.'

Write-Host '[6/6] Creating Desktop shortcuts and cleaning up retired artifacts...'
$shell = New-Object -ComObject WScript.Shell
$created = @()
foreach ($desktop in @((Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'), [Environment]::GetFolderPath('Desktop'))) {
  if (-not (Test-Path -LiteralPath $desktop)) { continue }
  foreach ($mode in @('vanilla', 'core')) {
    $label = if ($mode -eq 'vanilla') { 'OpenCode Vanilla' } else { 'OpenCode Core' }
    $path = Join-Path $desktop "$label.lnk"
    $shortcut = $shell.CreateShortcut($path)
    $shortcut.TargetPath = 'powershell.exe'
    $shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ModesDir\desktop-$mode.ps1`""
    $shortcut.WorkingDirectory = $env:USERPROFILE
    $shortcut.Description = "OpenCode Desktop in $mode mode"
    $shortcut.Save()
    $created += $path
  }
}
Write-Host "  created: $($created -join '; ')"
Write-Host '  the stock OpenCode shortcut was not modified.'

$LegacyFiles = @(
  (Join-Path $OcConfig 'agents\team-lead.md'),
  (Join-Path $OcConfig 'agents\team-scout.md'),
  (Join-Path $OcConfig 'agents\team-builder.md'),
  (Join-Path $OcConfig 'agents\team-reviewer.md'),
  (Join-Path $OcConfig 'commands\team.md'),
  (Join-Path $OcConfig 'ensemble.json'),
  (Join-Path $OcConfig 'ensemble.db'),
  (Join-Path $OcConfig 'ensemble.db-shm'),
  (Join-Path $OcConfig 'ensemble.db-wal'),
  (Join-Path $OcConfig 'profiles'),
  (Join-Path $Bin 'oc-product.cmd'),
  (Join-Path $env:APPDATA 'npm\oc-product.cmd')
)
# Shortcuts created by the retired two-mode design. The stock OpenCode shortcut is
# deliberately absent from this list.
foreach ($desktop in @((Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'), [Environment]::GetFolderPath('Desktop'))) {
  foreach ($label in @('OpenCode PRODUCT', 'OpenCode TEAM')) {
    $LegacyFiles += (Join-Path $desktop "$label.lnk")
  }
}
$Present = $LegacyFiles | Where-Object { Test-Path -LiteralPath $_ }
if ($Present.Count -eq 0) {
  Write-Host '  no retired artifacts found.'
} elseif ($CleanLegacy) {
  foreach ($item in $Present) {
    Remove-Item -LiteralPath $item -Recurse -Force
    Write-Host "  removed retired artifact: $item"
  }
} else {
  Write-Warning '  retired artifacts still present. Re-run with -CleanLegacy to remove them:'
  foreach ($item in $Present) { Write-Host "    $item" }
}

Write-Host ''
Write-Host 'Restore complete.'
Write-Host 'Modes: oc-vanilla (upstream Superpowers), oc-stable (cost-control lead), oc-core (autonomous Hackathon).'
Write-Host 'Desktop: stock OpenCode = Stable, plus OpenCode Vanilla and OpenCode Core shortcuts.'
Write-Host 'Next: authenticate providers, then run one of the oc-* commands or open a shortcut.'
