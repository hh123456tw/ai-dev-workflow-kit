param()

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

function Assert-True([bool]$Condition, [string]$Message) {
  if (-not $Condition) { throw "ACCEPTANCE FAILED: $Message" }
}

$teamLead = Get-Content -LiteralPath (Join-Path $Root 'agents\team-lead.md') -Raw
$teamCommand = Get-Content -LiteralPath (Join-Path $Root 'commands\team.md') -Raw
$teamProfile = Get-Content -LiteralPath (Join-Path $Root 'profiles\team\opencode.jsonc') -Raw | ConvertFrom-Json
$teamPolicy = Get-Content -LiteralPath (Join-Path $Root 'profiles\team\TEAM_MVP_SPRINT.md') -Raw

Assert-True ($teamCommand -match 'agent: team-lead') '/team must select team-lead'
Assert-True ($teamLead -match 'Build the demo spine first') 'global Team lead must state the Team principle'
Assert-True ($teamPolicy -match 'Wave 0: Recon') 'profile Team policy must define waves'
Assert-True ($teamPolicy -match 'Demo Survival Mode') 'profile Team policy must define time-pressure mode'
Assert-True ($teamLead -match 'at most two writable workers') 'global Team lead must cap writers at two'
Assert-True ($teamLead -notmatch 'spawn\s+EVERY\s+safe\s+ready\s+ticket') 'global Team lead must not use legacy eager DAG scheduling'
Assert-True ($teamLead -notmatch 'grill-me|to-tickets|Matt Pocock') 'global Team lead must not invoke Matt workflow'
Assert-True ($teamLead -notmatch '(?m)^model: ') 'global Team lead must inherit the configured model'
Assert-True (@($teamProfile.plugin) -contains '@hueyexe/opencode-ensemble@0.18.0') 'Team profile must pin Ensemble 0.18.0'
Assert-True (@($teamProfile.plugin) -contains 'superpowers@git+https://github.com/obra/superpowers.git') 'Team profile must load Superpowers'

$requiredPaths = @(
  'scripts\oc-team.ps1',
  'scripts\oc-team.sh',
  'profiles\team\agents\orchestrator.md'
)
foreach ($relative in $requiredPaths) {
  Assert-True (Test-Path -LiteralPath (Join-Path $Root $relative)) "missing $relative"
}

$teamPowerShellLauncher = Get-Content -LiteralPath (Join-Path $Root 'scripts\oc-team.ps1') -Raw
$teamBashLauncher = Get-Content -LiteralPath (Join-Path $Root 'scripts\oc-team.sh') -Raw
Assert-True ($teamPowerShellLauncher -match 'profiles\\team\\opencode\.jsonc') 'PowerShell Team launcher must reference profiles/team/opencode.jsonc'
Assert-True ($teamBashLauncher -match 'profiles/team/opencode\.jsonc') 'Bash Team launcher must reference profiles/team/opencode.jsonc'

'TEAM_MVP_SPRINT_ACCEPTANCE_PASS'
