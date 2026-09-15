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
Assert-True (@($team.plugin).Count -eq 0) 'TEAM must explicitly load no plugins'

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

Assert-True ($orchestrator -match 'Contract freeze gate') 'orchestrator must enforce contract freeze'
Assert-True ($orchestrator -match 'at most two implementation') 'orchestrator must enforce two DS attempts'
Assert-True ($orchestrator -match 'GPT-5\.6 takeover') 'orchestrator must define GPT takeover'
Assert-True ($worker -match 'model: deepseek/deepseek-flash') 'worker must route to verified DeepSeek model'
Assert-True ($worker -match 'steps: 15') 'worker must have a 15-step budget'
Assert-True ($worker -match '(?ms)task:\s*deny') 'worker must not spawn subagents'
Assert-True ($worker -match '(?ms)webfetch:\s*deny') 'worker web access must be denied'
Assert-True ($worker -match '\*\*/tests/\*\*') 'worker must have static test edit denial'
Assert-True ($reviewer -match 'model: openai/gpt-5\.6-sol') 'reviewer must route to verified GPT model'
Assert-True ($reviewer -match '(?ms)edit:\s*deny') 'reviewer must be read-only'

'PROFILE_BUNDLE_ACCEPTANCE_PASS'
