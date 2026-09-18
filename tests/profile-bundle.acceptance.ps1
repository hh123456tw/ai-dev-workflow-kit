param()

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

function Assert-True([bool]$Condition, [string]$Message) {
  if (-not $Condition) { throw "ACCEPTANCE FAILED: $Message" }
}

function Read-Text([string]$RelativePath) {
  $path = Join-Path $Root $RelativePath
  Assert-True (Test-Path -LiteralPath $path) "missing $RelativePath"
  return Get-Content -LiteralPath $path -Raw
}

function Read-Json([string]$RelativePath) {
  $path = Join-Path $Root $RelativePath
  Assert-True (Test-Path -LiteralPath $path) "missing $RelativePath"
  return Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
}

function Get-PermissionSection([string]$Content, [string]$Key) {
  $match = [regex]::Match($Content, "(?m)^  ${Key}:\r?\n((?:    \S.*(?:\r?\n|$))+)")
  if ($match.Success) { return $match.Groups[1].Value }
  return ''
}

# Returns the prompt body, excluding YAML frontmatter. The frontmatter legitimately
# names retired skills in order to deny them, so prose checks must ignore it.
function Get-Body([string]$Content) {
  $match = [regex]::Match($Content, '(?s)^---\r?\n.*?\r?\n---\r?\n(.*)$')
  if ($match.Success) { return $match.Groups[1].Value }
  return $Content
}

# --- Exactly one workflow -----------------------------------------------------

Assert-True (-not (Test-Path -LiteralPath (Join-Path $Root 'profiles\team\opencode.jsonc'))) 'the retired Team profile must not exist'
Assert-True (-not (Test-Path -LiteralPath (Join-Path $Root 'profiles\team\TEAM_MVP_SPRINT.md'))) 'the retired Team policy must not exist'
Assert-True (-not (Test-Path -LiteralPath (Join-Path $Root 'profiles\team\agents\orchestrator.md'))) 'the retired Team agents must not exist'
Assert-True (-not (Test-Path -LiteralPath (Join-Path $Root 'agents\team-lead.md'))) 'the retired team-lead agent must not exist'
Assert-True (-not (Test-Path -LiteralPath (Join-Path $Root 'commands\team.md'))) 'the retired /team command must not exist'
Assert-True (-not (Test-Path -LiteralPath (Join-Path $Root 'scripts\oc-team.ps1'))) 'the retired oc-team launcher must not exist'
Assert-True (-not (Test-Path -LiteralPath (Join-Path $Root 'scripts\oc-team.sh'))) 'the retired oc-team launcher must not exist'
Assert-True (Test-Path -LiteralPath (Join-Path $Root 'commands\stable.md')) '/stable must remain the entry command'
Assert-True (Test-Path -LiteralPath (Join-Path $Root 'scripts\oc-product.ps1')) 'oc-product launcher must remain'
Assert-True (Test-Path -LiteralPath (Join-Path $Root 'scripts\oc-product.sh')) 'oc-product launcher must remain'

$singleWorkflowSpec = Read-Text 'docs\superpowers\specs\2026-09-18-single-workflow-design.md'
Assert-True ($singleWorkflowSpec -match 'Keep exactly \*\*one workflow\*\*') 'the single-workflow spec must state the one-workflow decision'
Assert-True ($singleWorkflowSpec -match 'cost per successful slice') 'the spec must state the cost-per-successful-slice measurement rule'

# --- No multi-agent layer remains in active configuration ---------------------

$activeFiles = @(
  'profiles\product\opencode.jsonc',
  'global\opencode.jsonc',
  'agents\stable-lead.md',
  'AGENTS.md',
  'README.md'
)
foreach ($relative in $activeFiles) {
  $content = Read-Text $relative
  Assert-True ($content -notmatch 'opencode-ensemble') "$relative must not reference the retired Ensemble plugin"
  Assert-True ($content -notmatch '(?i)mattpocock/skills') "$relative must not install Matt skills"
}

# The setup scripts may name the retired plugin only to warn about leftovers; they
# must not install or copy any multi-agent artifact, and must offer to clean up.
foreach ($relative in @('scripts\setup-windows.ps1', 'scripts\setup-unix.sh')) {
  $content = Read-Text $relative
  Assert-True ($content -notmatch 'ensemble\.json\.template') "$relative must not install an Ensemble template"
  Assert-True ($content -notmatch '(?i)mattpocock/skills') "$relative must not install Matt skills"
  Assert-True ($content -match 'team-lead\.md') "$relative must list the retired team-lead agent for cleanup"
  Assert-True ($content -match 'ensemble\.json') "$relative must list the retired Ensemble config for cleanup"
}

# --- The single profile -------------------------------------------------------

$profile = Read-Json 'profiles\product\opencode.jsonc'
Assert-True ($null -ne $profile.permission) 'profile must use the current permission key'
Assert-True ($null -eq $profile.permissions) 'profile must not use the obsolete permissions key'
Assert-True ($null -eq $profile.agents) 'profile agents must be loaded from agents/*.md'
Assert-True ($null -eq $profile.instructions) 'profile must not duplicate policy in an instructions file'
Assert-True ($profile.default_agent -eq 'stable-lead') 'profile must default to the shared stable-lead definition'
Assert-True ($profile.subagent_depth -eq 1) 'profile subagent depth must be 1'
Assert-True ($profile.model -eq '{env:OPENCODE_PRIMARY_MODEL}') 'profile model must resolve from OPENCODE_PRIMARY_MODEL'
Assert-True ($profile.small_model -eq '{env:OPENCODE_WORKER_MODEL}') 'profile small_model must resolve from OPENCODE_WORKER_MODEL'
Assert-True (@($profile.plugin).Count -eq 1) 'profile must load exactly one plugin'
Assert-True (@($profile.plugin) -contains 'superpowers@git+https://github.com/obra/superpowers.git') 'profile must load Superpowers'

$secretPaths = @(
  '**/.env', '**/.env.*', '**/secrets/**', '**/credentials/**',
  '**/*credentials*', '**/*secret*', '**/*.pem', '**/*.key',
  '**/id_rsa', '**/id_ed25519'
)
foreach ($pattern in $secretPaths) {
  Assert-True ($profile.permission.read.PSObject.Properties[$pattern].Value -eq 'deny') "profile must deny reading $pattern"
  Assert-True ($profile.permission.edit.PSObject.Properties[$pattern].Value -eq 'deny') "profile must deny editing $pattern"
}
foreach ($command in @('git reset --hard*', 'git clean*', 'git branch -D*', 'git push --force*', 'git push -f*')) {
  Assert-True ($profile.permission.bash.PSObject.Properties[$command].Value -eq 'deny') "profile must deny '$command'"
}
foreach ($command in @('git rebase*', 'git push*')) {
  Assert-True ($profile.permission.bash.PSObject.Properties[$command].Value -eq 'ask') "profile must gate '$command'"
}

# --- The single lead definition ----------------------------------------------

$lead = Read-Text 'agents\stable-lead.md'
Assert-True ($lead -notmatch '(?m)^model:\s') 'lead must not pin a model; each surface config selects it'
Assert-True ($lead -match 'One workflow') 'lead must declare the single workflow'
Assert-True ($lead -match 'At most one writer is active at a time') 'lead must cap writers at one'
Assert-True ($lead -match 'Delegation is conditional, not automatic') 'lead must state the conditional delegation rule'
Assert-True ($lead -match 'its result can be reverted independently') 'lead must state the independent-rollback condition'
Assert-True ($lead -match 'Build the spine first') 'lead must state the spine-first principle'
Assert-True ($lead -match 'Progress is judged by artifacts') 'lead must judge progress by artifacts'
Assert-True ($lead -match 'Demo Survival') 'lead must define the Demo Survival phase'
Assert-True ($lead -match 'never invent a deadline') 'lead must not invent deadlines'
Assert-True ($lead -match 'cost per successful slice') 'lead must state the measurement rule'
Assert-True ($lead -match 'Workers never approve themselves') 'lead must forbid self-approval'

$legacyWorkflow = '(?i)matt\s+pocock|grill|to-spec|to-tickets|wayfinder|\bDAG\b|TEAM V2|Ensemble'
Assert-True ((Get-Body $lead) -notmatch $legacyWorkflow) 'lead body must not reference any retired workflow'
foreach ($skill in @('grill-me', 'to-tickets', 'implement', 'tdd', 'domain-modeling', 'codebase-design', 'handoff')) {
  Assert-True ($lead -match ('(?m)^    ' + [regex]::Escape($skill) + ': deny')) "lead must deny the retired skill $skill"
}

# --- Worker agents ------------------------------------------------------------

$requiredAgents = @('stable-lead.md', 'explorer.md', 'implementer.md', 'reviewer.md', 'test-writer.md')
foreach ($agent in $requiredAgents) {
  Assert-True (Test-Path -LiteralPath (Join-Path $Root "agents\$agent")) "missing agents\$agent"
}

$explorer = Read-Text 'agents\explorer.md'
$implementer = Read-Text 'agents\implementer.md'
$reviewer = Read-Text 'agents\reviewer.md'
$testWriter = Read-Text 'agents\test-writer.md'

foreach ($worker in @{ explorer = $explorer; implementer = $implementer; reviewer = $reviewer; 'test-writer' = $testWriter }.GetEnumerator()) {
  $name = $worker.Key
  $content = $worker.Value
  Assert-True ($content -match '(?m)^model: deepseek/deepseek-v4-flash\s*$') "$name must route to the DeepSeek worker model"
  Assert-True ((Get-Body $content) -notmatch $legacyWorkflow) "$name body must not reference any retired workflow"
  Assert-True ($content -match '(?m)^  task: deny\s*$') "$name must not spawn subagents"
  Assert-True ($content -match '(?m)^  webfetch: deny\s*$') "$name must not reach the web"
  $readSection = Get-PermissionSection $content 'read'
  Assert-True ($readSection.Length -gt 0) "$name must define read permissions"
  Assert-True ($readSection -notmatch '(?m)^  \S+:') "$name read section must stop before the next permission key"
  Assert-True (([regex]::Matches($readSection, '":\s*deny')).Count -eq $secretPaths.Count) "$name read section must contain exactly the secret denials"
}

foreach ($readOnly in @{ explorer = $explorer; reviewer = $reviewer }.GetEnumerator()) {
  Assert-True ($readOnly.Value -match '(?m)^  edit: deny\s*$') "$($readOnly.Key) must be read-only"
}

$implementerEdit = Get-PermissionSection $implementer 'edit'
Assert-True ($implementerEdit -match '"\*":\s*allow') 'implementer must retain normal edit allow'
Assert-True (([regex]::Matches($implementerEdit, '":\s*deny')).Count -eq $secretPaths.Count) 'implementer edit section must contain exactly the secret denials'
$implementerBash = Get-PermissionSection $implementer 'bash'
foreach ($command in @('git push*', 'git commit*', 'git merge*', 'git rebase*', 'git reset --hard*', 'git clean*', 'git branch -D*', 'rm -rf*')) {
  $quoted = '"' + [regex]::Escape($command) + '":\s*deny'
  Assert-True ($implementerBash -match $quoted) "implementer must deny '$command'"
}

Assert-True ($implementer -match '(?m)^## Completion handback\s*$') 'implementer must use the exact Completion handback heading'
foreach ($bullet in @('- Changed files', '- Commands run and exact result', '- Core acceptance result', '- Remaining limitation or blocker')) {
  Assert-True ($implementer -match ('(?m)^' + [regex]::Escape($bullet) + '\s*$')) "implementer handback must include '$bullet'"
}

$testWriterEdit = Get-PermissionSection $testWriter 'edit'
Assert-True ($testWriterEdit -match '"\*":\s*deny') 'test-writer must default to denying edits'
Assert-True ($testWriterEdit -match '\*\*/tests/\*\*":\s*allow') 'test-writer must be allowed to edit test paths'

# --- Documentation and setup --------------------------------------------------

$readme = Read-Text 'README.md'
Assert-True ($readme -match '單一工作流') 'README must describe a single workflow'
Assert-True ($readme -notmatch '/team') 'README must not advertise the retired /team entry'
Assert-True ($readme -notmatch 'oc-team') 'README must not advertise the retired oc-team launcher'
Assert-True ($readme -match 'oc-product') 'README must document the oc-product launcher'

$agentsDoc = Read-Text 'AGENTS.md'
Assert-True ($agentsDoc -match 'One workflow') 'AGENTS.md must declare one workflow'
Assert-True ($agentsDoc -notmatch '/team') 'AGENTS.md must not advertise the retired /team entry'
Assert-True ($agentsDoc -match 'cost per successful slice') 'AGENTS.md must state the measurement rule'

$setupWin = Read-Text 'scripts\setup-windows.ps1'
$setupUnix = Read-Text 'scripts\setup-unix.sh'
Assert-True ($setupWin -match 'CleanLegacy') 'Windows setup must offer the legacy cleanup switch'
Assert-True ($setupUnix -match '--clean-legacy') 'Unix setup must offer the legacy cleanup flag'
Assert-True ($setupWin -notmatch 'oc-team') 'Windows setup must not install the retired launcher'
Assert-True ($setupUnix -notmatch 'oc-team') 'Unix setup must not install the retired launcher'
Assert-True ($setupWin -match "stable-lead\.md") 'Windows setup must deploy the lead definition'
Assert-True ($setupUnix -match 'stable-lead\.md') 'Unix setup must deploy the lead definition'

'PROFILE_BUNDLE_ACCEPTANCE_PASS'
