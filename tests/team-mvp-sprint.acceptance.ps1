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
$requiredSections = @(
  'Core Principle',
  'Wave 0: Recon',
  'Wave 1: Spine',
  'Wave 2: Independent Expansion',
  'Wave 3: Integration',
  'Wave 4: QA',
  'Wave 5: Demo Hardening',
  'Parallelization Rubric',
  'Artifact-Based Recovery',
  'Time-Pressure Modes'
)
foreach ($section in $requiredSections) {
  Assert-True ($teamPolicy -match ('(?m)^## ' + [regex]::Escape($section) + '\s*$')) "profile Team policy must define $section"
}
Assert-True ($teamPolicy -match 'Build the demo spine first\. Parallelize discovery freely\. Parallelize code only when ownership is provably independent\. Integrate every wave before spawning the next\. Optimize for time-to-demo, not agent utilization\.') 'profile Team policy must state the exact Team philosophy'
Assert-True ($teamPolicy -match 'Demo Survival Mode') 'profile Team policy must define time-pressure mode'
Assert-True ($teamLead -match 'at most two writable workers') 'global Team lead must cap writers at two'
Assert-True ($teamLead -notmatch 'spawn\s+EVERY\s+safe\s+ready\s+ticket') 'global Team lead must not use legacy eager DAG scheduling'
Assert-True ($teamLead -notmatch 'grill-me|to-tickets|Matt Pocock') 'global Team lead must not invoke Matt workflow'
Assert-True ($teamLead -notmatch '(?m)^model: ') 'global Team lead must inherit the configured model'
Assert-True (@($teamProfile.plugin) -contains '@hueyexe/opencode-ensemble@0.18.0') 'Team profile must pin Ensemble 0.18.0'
Assert-True (@($teamProfile.plugin) -contains 'superpowers@git+https://github.com/obra/superpowers.git') 'Team profile must load Superpowers'

$teamAgentPaths = @(
  'agents\team-scout.md',
  'agents\team-builder.md',
  'agents\team-reviewer.md'
)
$legacyTeamWorkflow = '(?i)matt\s+pocock|grill|to-spec|to-tickets|ticket|\bDAG\b'
foreach ($relative in $teamAgentPaths) {
  $path = Join-Path $Root $relative
  Assert-True (Test-Path -LiteralPath $path) "missing $relative"
  $content = Get-Content -LiteralPath $path -Raw
  Assert-True ($content -notmatch $legacyTeamWorkflow) "Team agent $relative must not contain legacy workflow text"
  Assert-True ($content -notmatch '(?m)^model: ') "Team agent $relative must inherit the configured model"
  Assert-True ($content -match '(?m)^  task:\s*deny\s*$') "Team agent $relative must not spawn subagents"
}

$teamScout = Get-Content -LiteralPath (Join-Path $Root 'agents\team-scout.md') -Raw
$teamBuilder = Get-Content -LiteralPath (Join-Path $Root 'agents\team-builder.md') -Raw
$teamReviewer = Get-Content -LiteralPath (Join-Path $Root 'agents\team-reviewer.md') -Raw
Assert-True ($teamScout -match '(?m)^  edit:\s*deny\s*$') 'team-scout must be read-only'
Assert-True ($teamBuilder -match '(?m)^## Completion handback\s*$') 'team-builder must require evidence-based handback'
Assert-True ($teamBuilder -match '(?m)^  webfetch:\s*deny\s*$') 'team-builder web access must be denied'
Assert-True ($teamReviewer -match '(?m)^  edit:\s*deny\s*$') 'team-reviewer must be read-only'

$secretPaths = @(
  '**/.env', '**/.env.*', '**/secrets/**', '**/credentials/**',
  '**/*credentials*', '**/*secret*', '**/*.pem', '**/*.key',
  '**/id_rsa', '**/id_ed25519'
)
function Get-PermissionSection([string]$Content, [string]$Key) {
  $match = [regex]::Match($Content, "(?m)^  ${Key}:\r?\n((?:    \S.*(?:\r?\n|$))+)")
  if ($match.Success) { return $match.Groups[1].Value }
  return ''
}
$teamAgents = [ordered]@{
  'team-scout' = $teamScout
  'team-builder' = $teamBuilder
  'team-reviewer' = $teamReviewer
}
foreach ($name in $teamAgents.Keys) {
  $readSection = Get-PermissionSection $teamAgents[$name] 'read'
  Assert-True ($readSection.Length -gt 0) "$name must define read permissions"
  Assert-True ($readSection -notmatch '(?m)^  \S+:') "$name read section must stop before the next permission key"
  Assert-True (([regex]::Matches($readSection, '":\s*deny')).Count -eq $secretPaths.Count) "$name read section must contain exactly the secret denials"
  foreach ($pattern in $secretPaths) {
    $quoted = '"' + [regex]::Escape($pattern) + '":\s*deny'
    Assert-True ($readSection -match $quoted) "$name must deny reading $pattern"
  }
}

$builderEditSection = Get-PermissionSection $teamBuilder 'edit'
Assert-True ($builderEditSection -match '"\*":\s*allow') 'team-builder must retain normal edit allow'
Assert-True ($builderEditSection -notmatch '(?m)^  \S+:') 'team-builder edit section must stop before the next permission key'
Assert-True (([regex]::Matches($builderEditSection, '":\s*deny')).Count -eq $secretPaths.Count) 'team-builder edit section must contain exactly the secret denials'
foreach ($pattern in $secretPaths) {
  $quoted = '"' + [regex]::Escape($pattern) + '":\s*deny'
  Assert-True ($builderEditSection -match $quoted) "team-builder must deny editing $pattern"
}

$builderBashSection = Get-PermissionSection $teamBuilder 'bash'
Assert-True ($builderBashSection -notmatch '(?m)^  \S+:') 'team-builder bash section must stop before the next permission key'
$destructiveGit = @(
  'git reset --hard', 'git clean', 'git branch -D', 'git push --force',
  'git push -f', 'git push', 'git commit', 'git merge', 'git rebase'
)
foreach ($command in $destructiveGit) {
  $quoted = '"' + [regex]::Escape($command) + '\*":\s*deny'
  Assert-True ($builderBashSection -match $quoted) "team-builder must deny '$command*'"
}

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
