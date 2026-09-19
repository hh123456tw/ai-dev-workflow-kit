# Runtime isolation verification for the three modes.
# Asserts the resolved OpenCode config and skill set for each mode, rather than
# grepping launcher text. Requires `opencode` on PATH and setup to have run.
$ErrorActionPreference = 'Stop'

$OcConfig = Join-Path $env:USERPROFILE '.config\opencode'
$failures = @()

function Get-ResolvedConfig([string]$mode) {
  $dir = Join-Path $OcConfig "modes\$mode"
  $config = Join-Path $dir 'opencode.jsonc'
  if (-not (Test-Path -LiteralPath $config)) { throw "Mode '$mode' is not deployed at $dir. Run setup first." }
  $env:OPENCODE_CONFIG = $config
  $env:OPENCODE_CONFIG_DIR = $null
  $env:XDG_CONFIG_HOME = $null
  $env:OPENCODE_DISABLE_EXTERNAL_SKILLS = $null
  $env:OPENCODE_DISABLE_DEFAULT_PLUGINS = $null
  if ($mode -eq 'core') {
    $env:OPENCODE_CONFIG_DIR = $dir
    $env:XDG_CONFIG_HOME = Join-Path $dir 'xdg'
    $env:OPENCODE_DISABLE_EXTERNAL_SKILLS = '1'
    $env:OPENCODE_DISABLE_DEFAULT_PLUGINS = '1'
  }
  $pure = if ($mode -eq 'core') { '--pure' } else { $null }
  $configJson = if ($pure) { opencode debug config --pure 2>&1 | Out-String } else { opencode debug config 2>&1 | Out-String }
  $skillJson = if ($pure) { opencode debug skill --pure 2>&1 | Out-String } else { opencode debug skill 2>&1 | Out-String }
  return @{ config = ($configJson | ConvertFrom-Json); skills = $skillJson }
}

function Assert-True([bool]$Condition, [string]$Message) {
  if ($Condition) {
    Write-Host "  PASS: $Message"
  } else {
    Write-Host "  FAIL: $Message" -ForegroundColor Red
    $script:failures += $Message
  }
}

function Test-Skill([string]$skillJson, [string]$name) {
  return $skillJson -match ('"name": "' + [regex]::Escape($name) + '"')
}

$superpowersSpec = 'superpowers@git+https://github.com/obra/superpowers.git'
$coreSkills = @(
  'test-driven-development', 'systematic-debugging', 'verification-before-completion',
  'requesting-code-review', 'receiving-code-review', 'finishing-a-development-branch'
)
$heavySkills = @('brainstorming', 'writing-plans', 'subagent-driven-development', 'using-git-worktrees')

Write-Host 'Vanilla:'
$vanilla = Get-ResolvedConfig 'vanilla'
Assert-True ($vanilla.config.default_agent -eq 'build') 'default_agent is build'
Assert-True (@($vanilla.config.plugin) -contains $superpowersSpec) 'full Superpowers plugin is loaded'
Assert-True ($vanilla.config.model -eq 'openai/gpt-5.6-sol') 'primary model is pinned'
foreach ($skill in @('brainstorming', 'subagent-driven-development', 'test-driven-development')) {
  Assert-True (Test-Skill $vanilla.skills $skill) "skill visible: $skill"
}

Write-Host 'Stable:'
$stable = Get-ResolvedConfig 'stable'
Assert-True ($stable.config.default_agent -eq 'stable-lead') 'default_agent is stable-lead'
Assert-True (@($stable.config.plugin) -contains $superpowersSpec) 'full Superpowers plugin is loaded'
foreach ($skill in @('brainstorming', 'subagent-driven-development', 'test-driven-development')) {
  Assert-True (Test-Skill $stable.skills $skill) "skill visible: $skill"
}

Write-Host 'Core:'
$core = Get-ResolvedConfig 'core'
Assert-True ($core.config.default_agent -eq 'core-lead') 'default_agent is core-lead'
Assert-True (@($core.config.plugin).Count -eq 0) 'no plugin is loaded'
Assert-True ($core.config.model -eq 'openai/gpt-5.6-sol') 'primary model is pinned'
foreach ($skill in $coreSkills) {
  Assert-True (Test-Skill $core.skills $skill) "Core skill visible: $skill"
}
foreach ($skill in $heavySkills) {
  Assert-True (-not (Test-Skill $core.skills $skill)) "heavy skill hidden: $skill"
}

$env:OPENCODE_CONFIG = $null
$env:OPENCODE_CONFIG_DIR = $null
$env:XDG_CONFIG_HOME = $null
$env:OPENCODE_DISABLE_EXTERNAL_SKILLS = $null
$env:OPENCODE_DISABLE_DEFAULT_PLUGINS = $null

if ($failures.Count -gt 0) {
  Write-Host ''
  Write-Host "MODE_ISOLATION_FAILED ($($failures.Count))" -ForegroundColor Red
  exit 1
}
Write-Host ''
Write-Host 'MODE_ISOLATION_PASS'
