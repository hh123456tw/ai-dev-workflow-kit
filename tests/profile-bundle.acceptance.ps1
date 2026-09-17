param()

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

function Assert-True([bool]$Condition, [string]$Message) {
  if (-not $Condition) { throw "ACCEPTANCE FAILED: $Message" }
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

$team = Read-Json 'profiles\team\opencode.jsonc'
$product = Read-Json 'profiles\product\opencode.jsonc'

Assert-True ($null -ne $team.permission) 'TEAM must use current permission key'
Assert-True ($null -eq $team.permissions) 'TEAM must not use obsolete permissions key'
Assert-True ($null -eq $team.agents) 'TEAM agents must be loaded from agents/*.md, not obsolete agents key'
Assert-True ($team.default_agent -eq 'orchestrator') 'TEAM default agent must be orchestrator'
Assert-True ($team.subagent_depth -eq 1) 'TEAM subagent depth must be 1'
Assert-True (@($team.plugin) -contains '@hueyexe/opencode-ensemble@0.18.0') 'TEAM must pin Ensemble 0.18.0'
Assert-True (@($team.plugin) -contains 'superpowers@git+https://github.com/obra/superpowers.git') 'TEAM must load Superpowers'
Assert-True (@($team.plugin).Count -eq 2) 'TEAM must load exactly Superpowers and Ensemble'
Assert-True ($team.model -eq '{env:OPENCODE_PRIMARY_MODEL}') 'TEAM model must resolve from OPENCODE_PRIMARY_MODEL'
Assert-True ($team.small_model -eq '{env:OPENCODE_WORKER_MODEL}') 'TEAM small_model must resolve from OPENCODE_WORKER_MODEL'
Assert-True (@($team.instructions) -contains './TEAM_MVP_SPRINT.md') 'TEAM instructions must point to TEAM_MVP_SPRINT.md'

Assert-True ($null -ne $team.agent) 'TEAM must route agent models through the config agent block'
Assert-True ($team.agent.orchestrator.model -eq '{env:OPENCODE_PRIMARY_MODEL}') 'TEAM orchestrator must resolve the primary model from config'
Assert-True ($team.agent.'ds-worker'.model -eq '{env:OPENCODE_WORKER_MODEL}') 'TEAM ds-worker must resolve the worker model from config'
Assert-True ($team.agent.researcher.model -eq '{env:OPENCODE_WORKER_MODEL}') 'TEAM researcher must resolve the worker model from config'
Assert-True ($team.agent.reviewer.model -eq '{env:OPENCODE_WORKER_MODEL}') 'TEAM reviewer must resolve the worker model from config'

$approvedSuperpowers = @(
  'brainstorming', 'dispatching-parallel-agents', 'executing-plans',
  'finishing-a-development-branch', 'receiving-code-review', 'requesting-code-review',
  'subagent-driven-development', 'systematic-debugging', 'test-driven-development',
  'using-git-worktrees', 'using-superpowers', 'verification-before-completion',
  'writing-plans', 'writing-skills'
)
$approvedGstack = @('qa', 'qa-only', 'review', 'ship', 'cso', 'investigate', 'plan-ceo-review', 'design-review', 'benchmark')
$approvedSkills = @($approvedSuperpowers + $approvedGstack)
$allowedSkills = @($team.permission.skill.PSObject.Properties | Where-Object { $_.Value -eq 'allow' } | ForEach-Object { $_.Name })
Assert-True ($team.permission.skill.'*' -eq 'deny') 'TEAM skill default must be deny'
Assert-True ($approvedSuperpowers.Count -eq 14) 'the approved Superpowers allowlist must contain 14 skills'
Assert-True ($approvedGstack.Count -eq 9) 'the approved gstack allowlist must contain 9 skills'
Assert-True ($allowedSkills.Count -eq 23) 'TEAM skill allowlist must contain exactly 23 entries'
Assert-True ((Compare-Object $approvedSkills $allowedSkills).Count -eq 0) 'TEAM skill allowlist must be exactly the approved Superpowers plus gstack skills'
foreach ($legacySkill in @('setup-matt-pocock-skills', 'grill-with-docs', 'grill-me', 'wayfinder', 'to-spec', 'to-tickets', 'implement', 'tdd', 'codebase-design', 'domain-modeling', 'diagnosing-bugs', 'code-review', 'research', 'handoff')) {
  Assert-True ($allowedSkills -notcontains $legacySkill) "TEAM must not allow legacy skill $legacySkill"
}

$secretPaths = @(
  '**/.env', '**/.env.*', '**/secrets/**', '**/credentials/**',
  '**/*credentials*', '**/*secret*', '**/*.pem', '**/*.key',
  '**/id_rsa', '**/id_ed25519'
)
foreach ($pattern in $secretPaths) {
  Assert-True ($team.permission.read.PSObject.Properties[$pattern].Value -eq 'deny') "TEAM profile must deny reading $pattern"
  Assert-True ($team.permission.edit.PSObject.Properties[$pattern].Value -eq 'deny') "TEAM profile must deny editing $pattern"
}
foreach ($command in @('git reset --hard*', 'git clean*', 'git branch -D*', 'git push --force*', 'git push -f*')) {
  Assert-True ($team.permission.bash.PSObject.Properties[$command].Value -eq 'deny') "TEAM profile must deny '$command'"
}
foreach ($command in @('git rebase*', 'git push*')) {
  Assert-True ($team.permission.bash.PSObject.Properties[$command].Value -eq 'ask') "TEAM profile must gate '$command'"
}

Assert-True ($null -ne $product.permission) 'PRODUCT must use current permission key'
Assert-True ($null -eq $product.permissions) 'PRODUCT must not use obsolete permissions key'
Assert-True ($null -eq $product.agents) 'PRODUCT agents must be loaded from agents/*.md'
Assert-True ($product.default_agent -eq 'product') 'PRODUCT default agent must be product'
Assert-True ($product.subagent_depth -eq 1) 'PRODUCT subagent depth must be 1'
Assert-True (@($product.plugin) -contains 'superpowers@git+https://github.com/obra/superpowers.git') 'PRODUCT must retain Superpowers'

$requiredAgents = @(
  'profiles\team\agents\orchestrator.md',
  'profiles\team\agents\ds-worker.md',
  'profiles\team\agents\reviewer.md',
  'profiles\team\agents\researcher.md',
  'profiles\product\agents\product.md'
)
foreach ($relative in $requiredAgents) {
  Assert-True (Test-Path -LiteralPath (Join-Path $Root $relative)) "missing $relative"
}

$orchestrator = Get-Content -LiteralPath (Join-Path $Root 'profiles\team\agents\orchestrator.md') -Raw
$worker = Get-Content -LiteralPath (Join-Path $Root 'profiles\team\agents\ds-worker.md') -Raw
$reviewer = Get-Content -LiteralPath (Join-Path $Root 'profiles\team\agents\reviewer.md') -Raw
$researcher = Get-Content -LiteralPath (Join-Path $Root 'profiles\team\agents\researcher.md') -Raw

Assert-True ($orchestrator -match 'Parallelize discovery freely') 'orchestrator must use discovery-first policy'
Assert-True ($worker -match 'Completion handback') 'worker must require evidence-based handback'
Assert-True ($worker -match '(?ms)task:\s*deny') 'worker must not spawn subagents'
Assert-True ($worker -match '(?ms)webfetch:\s*deny') 'worker web access must be denied'
Assert-True ($reviewer -match '(?ms)edit:\s*deny') 'reviewer must be read-only'
Assert-True ($researcher -match 'read-only scout') 'researcher must remain read-only'

Assert-True ($worker -match '(?m)^## Completion handback\s*$') 'worker must use the exact Completion handback heading'
foreach ($bullet in @('- Changed files', '- Commands run and exact result', '- Core acceptance result', '- Remaining limitation or blocker')) {
  Assert-True ($worker -match ('(?m)^' + [regex]::Escape($bullet) + '\s*$')) "worker handback must include '$bullet'"
}
Assert-True ($worker -match '(?m)^  task: deny\s*$') 'worker must declare a flat task: deny line'
Assert-True ($worker -match '(?m)^  webfetch: deny\s*$') 'worker must declare a flat webfetch: deny line'
Assert-True ($worker -notmatch '\*\*/tests/\*\*|\*\*/docs/\*\*|\*\*/migrations/\*\*') 'worker must not blanket-deny test/docs/migration edits'
Assert-True ($reviewer -match '(?m)^  edit: deny\s*$') 'reviewer must declare a flat edit: deny line'
Assert-True ($reviewer -match '(?m)^  task: deny\s*$') 'reviewer must not spawn subagents'
Assert-True ($researcher -match '(?m)^  edit: deny\s*$') 'researcher must declare a flat edit: deny line'
Assert-True ($researcher -match '(?m)^  task: deny\s*$') 'researcher must not spawn subagents'

$workerReadSection = Get-PermissionSection $worker 'read'
Assert-True ($workerReadSection.Length -gt 0) 'worker must define read permissions'
Assert-True ($workerReadSection -notmatch '(?m)^  \S+:') 'worker read section must stop before the next permission key'
Assert-True (([regex]::Matches($workerReadSection, '":\s*deny')).Count -eq $secretPaths.Count) 'worker read section must contain exactly the secret denials'
$workerEditSection = Get-PermissionSection $worker 'edit'
Assert-True ($workerEditSection -match '"\*":\s*allow') 'worker must retain normal edit allow'
Assert-True ($workerEditSection -notmatch '(?m)^  \S+:') 'worker edit section must stop before the next permission key'
Assert-True (([regex]::Matches($workerEditSection, '":\s*deny')).Count -eq $secretPaths.Count) 'worker edit section must contain exactly the secret denials'
$workerBashSection = Get-PermissionSection $worker 'bash'
Assert-True ($workerBashSection -notmatch '(?m)^  \S+:') 'worker bash section must stop before the next permission key'
foreach ($command in @('git push*', 'git merge*', 'git rebase*', 'git reset*', 'git clean*', 'git branch -D*')) {
  $quoted = '"' + [regex]::Escape($command) + '":\s*deny'
  Assert-True ($workerBashSection -match $quoted) "worker must deny '$command'"
}

$profileAgents = @{
  'orchestrator' = $orchestrator
  'ds-worker' = $worker
  'reviewer' = $reviewer
  'researcher' = $researcher
}
$legacyProfileWorkflow = '(?i)matt\s+pocock|grill|to-spec|to-tickets|\btickets?\b|\bDAG\b|wayfinder|TEAM V2'
foreach ($name in $profileAgents.Keys) {
  Assert-True ($profileAgents[$name] -notmatch $legacyProfileWorkflow) "Team profile agent $name must not contain legacy workflow text"
  Assert-True ($profileAgents[$name] -notmatch '(?m)^model:\s') "Team profile agent $name must not set a frontmatter model; env interpolation is unsupported there"
}
$teamPolicy = Get-Content -LiteralPath (Join-Path $Root 'profiles\team\TEAM_MVP_SPRINT.md') -Raw
Assert-True ($teamPolicy -notmatch $legacyProfileWorkflow) 'Team profile policy must not contain legacy workflow text'

$ensembleTemplate = Get-Content -LiteralPath (Join-Path $Root 'profiles\team\ensemble.json.template') -Raw | ConvertFrom-Json
Assert-True ($ensembleTemplate.mergeOnCleanup -eq $false) 'Ensemble template must not auto-merge on cleanup'
Assert-True ([int]$ensembleTemplate.stallThresholdMs -gt 0) 'Ensemble template must set a finite stall threshold'
Assert-True ([int]$ensembleTemplate.timeoutMs -gt 0) 'Ensemble template must set a finite timeout'
Assert-True ($ensembleTemplate.defaultModel -eq '__OPENCODE_WORKER_MODEL__') 'Ensemble template default model must be the worker placeholder'
foreach ($role in @('ds-worker', 'researcher', 'reviewer')) {
  $mapped = $ensembleTemplate.modelsByAgent.PSObject.Properties[$role].Value
  Assert-True ($mapped -eq '__OPENCODE_WORKER_MODEL__') "Ensemble template must route $role to the worker model"
}
Assert-True ($null -eq $ensembleTemplate.PSObject.Properties['maxAgents']) 'Ensemble template must not encode agent-count policy'

'PROFILE_BUNDLE_ACCEPTANCE_PASS'
