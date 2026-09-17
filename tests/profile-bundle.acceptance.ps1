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

$team = Read-Json 'profiles\team\opencode.jsonc'
$product = Read-Json 'profiles\product\opencode.jsonc'

Assert-True ($null -ne $team.permission) 'TEAM must use current permission key'
Assert-True ($null -eq $team.permissions) 'TEAM must not use obsolete permissions key'
Assert-True ($null -eq $team.agents) 'TEAM agents must be loaded from agents/*.md, not obsolete agents key'
Assert-True ($team.default_agent -eq 'orchestrator') 'TEAM default agent must be orchestrator'
Assert-True ($team.subagent_depth -eq 1) 'TEAM subagent depth must be 1'
Assert-True (@($team.plugin) -contains '@hueyexe/opencode-ensemble@0.18.0') 'TEAM must pin Ensemble 0.18.0'
Assert-True (@($team.plugin) -contains 'superpowers@git+https://github.com/obra/superpowers.git') 'TEAM must load Superpowers'

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

'PROFILE_BUNDLE_ACCEPTANCE_PASS'
