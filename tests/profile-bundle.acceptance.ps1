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

function Get-Body([string]$Content) {
  $match = [regex]::Match($Content, '(?s)^---\r?\n.*?\r?\n---\r?\n(.*)$')
  if ($match.Success) { return $match.Groups[1].Value }
  return $Content
}

function Get-Flat([string]$Content) {
  return ($Content -replace '\s+', ' ')
}

function Get-Section([string]$Content, [string]$Heading) {
  $pattern = '(?ms)^## ' + [regex]::Escape($Heading) + '\s*$(.*?)(?=^## |\Z)'
  $match = [regex]::Match($Content, $pattern)
  if ($match.Success) { return $match.Groups[1].Value }
  return ''
}

function Assert-CoreClearsDefaultPlugins([string]$Content, [string]$Label) {
  # Core must actively clear an inherited OPENCODE_DISABLE_DEFAULT_PLUGINS and
  # must never assign it on: default provider plugins are required to resolve
  # the pinned model. A static "does not mention the variable" check is not
  # enough, because the clear form necessarily names it.
  Assert-True ($Content -notmatch '(?m)\$env:OPENCODE_DISABLE_DEFAULT_PLUGINS\s*=') "$Label must not set `$env:OPENCODE_DISABLE_DEFAULT_PLUGINS: default provider plugins are required for model resolution"
  Assert-True ($Content -notmatch '(?m)export\s+OPENCODE_DISABLE_DEFAULT_PLUGINS\s*=') "$Label must not export OPENCODE_DISABLE_DEFAULT_PLUGINS: default provider plugins are required for model resolution"
  Assert-True ($Content -match '(?m)Remove-Item\s+Env:OPENCODE_DISABLE_DEFAULT_PLUGINS|(?m)^\s*unset\s+OPENCODE_DISABLE_DEFAULT_PLUGINS') "$Label must clear an inherited OPENCODE_DISABLE_DEFAULT_PLUGINS so default provider plugins stay enabled"
}

$coreSkills = @(
  'test-driven-development',
  'systematic-debugging',
  'verification-before-completion',
  'requesting-code-review',
  'receiving-code-review',
  'finishing-a-development-branch'
)
$heavySkills = @('brainstorming', 'writing-plans', 'subagent-driven-development', 'using-git-worktrees')
$legacyWorkflow = '(?i)matt\s+pocock|grill|to-spec|to-tickets|wayfinder|\bDAG\b|TEAM V2|Ensemble'

# --- Three isolated modes -----------------------------------------------------

$vanilla = Read-Json 'modes\vanilla\opencode.jsonc'
$stable = Read-Json 'modes\stable\opencode.jsonc'
$core = Read-Json 'modes\core\opencode.jsonc'
$coreCodeGraph = Read-Json 'modes\core\opencode-codegraph.jsonc'

Assert-True ($vanilla.default_agent -eq 'build') 'Vanilla must default to the upstream build agent'
Assert-True ($stable.default_agent -eq 'stable-lead') 'Stable must default to stable-lead'
Assert-True ($core.default_agent -eq 'core-lead') 'Core must default to core-lead'

foreach ($pair in @(@('vanilla', $vanilla), @('stable', $stable), @('core', $core))) {
  $name = $pair[0]; $config = $pair[1]
  Assert-True ($config.model -eq 'openai/gpt-5.6-sol') "$name must pin the primary model"
  Assert-True ($config.small_model -eq 'deepseek/deepseek-v4-flash') "$name must pin the worker model"
}

$superpowersSpec = 'superpowers@git+https://github.com/obra/superpowers.git'
Assert-True (@($vanilla.plugin) -contains $superpowersSpec) 'Vanilla must load full Superpowers'
Assert-True (@($stable.plugin) -contains $superpowersSpec) 'Stable must load full Superpowers'
Assert-True ($null -eq $core.plugin) 'Core must not declare any plugin'
Assert-True ($core.subagent_depth -eq 1) 'Core must limit subagent depth to 1'
Assert-True ($null -eq $core.mcp) 'Core control must not load CodeGraph or another MCP'
Assert-True ($coreCodeGraph.default_agent -eq 'core-lead') 'CodeGraph canary must keep core-lead'
Assert-True ($coreCodeGraph.mcp.codegraph.type -eq 'local') 'CodeGraph canary must use a local MCP'
Assert-True ($coreCodeGraph.mcp.codegraph.command[0] -match 'v0\.20\.1') 'CodeGraph canary must pin version 0.20.1'
Assert-True (($coreCodeGraph.mcp.codegraph.command -join ' ') -match '--mcp --profile=core') 'CodeGraph canary must expose only the upstream core tool profile'

# Core skills are deployed from the installed package, never vendored
$gitignore = Read-Text '.gitignore'
Assert-True ($gitignore -match 'modes/core/skills/') 'Core skills directory must be git-ignored'
Assert-True (-not (Test-Path -LiteralPath (Join-Path $Root 'modes\core\skills\test-driven-development'))) 'Core skills must not be vendored into the repository'

# --- Core lead definition -----------------------------------------------------

$coreLead = Read-Text 'modes\core\agents\core-lead.md'
Assert-True ($coreLead -notmatch '(?m)^model:\s') 'core-lead must not pin a model; the mode config selects it'
Assert-True ((Get-Body $coreLead) -notmatch $legacyWorkflow) 'core-lead body must not reference any retired workflow'
$flatCoreLead = Get-Flat $coreLead
Assert-True ($flatCoreLead -match 'Start immediately') 'core-lead must start immediately instead of gating on design approval'
Assert-True ($flatCoreLead -match 'irreversible or destructive') 'core-lead must stop for irreversible or destructive actions'
Assert-True ($flatCoreLead -match 'security- or credential-sensitive') 'core-lead must stop for security or credential decisions'
Assert-True ($flatCoreLead -match 'destructive data or schema migration') 'core-lead must stop for destructive migrations'
Assert-True ($flatCoreLead -match 'At most one writer is active at a time') 'core-lead must cap writers at one'

foreach ($skill in $coreSkills) {
  Assert-True ($coreLead -match ('(?m)^    ' + [regex]::Escape($skill) + ': allow')) "core-lead must allow the Core skill $skill"
}
foreach ($skill in $heavySkills) {
  Assert-True ($coreLead -notmatch ('(?m)^    ' + [regex]::Escape($skill) + ': allow')) "core-lead must not allow the heavy skill $skill"
}
Assert-True ($coreLead -match '(?m)^    "\*": deny\s*$') 'core-lead must deny unlisted skills by default'

# --- Core completion gate and real-path evidence ------------------------------
# Baseline finding: every valid run claimed completion before a required check
# passed, and one run shipped with its reviewer dispatch denied. An unavailable
# reviewer must block completion, not silently pass it. A second finding: Core
# verified a "<20% warm time" criterion with a synthetic counter while the measured
# real ratio was 0.335 (false green). These are static policy-content checks; the
# Phase 3 revalidation measures whether a live model obeys them.

$completionGate = Get-Flat (Get-Section $coreLead 'Completion gate')
Assert-True ($completionGate.Length -gt 0) 'core-lead must define a Completion gate section'
foreach ($field in @('deadline mode', 'changed-file count', 'file classifications', 'risk flags', 'exact result and exit codes', 'acceptance coverage', 'reviewer status', 'scope statement', 'blocked condition')) {
  Assert-True ($completionGate -match [regex]::Escape($field)) "core-lead Completion gate must require the '$field' field"
}
Assert-True ($completionGate -match 'verification_blocked') 'core-lead must mark an unavailable reviewer as verification_blocked'
Assert-True ($completionGate -match 'do not claim done') 'core-lead must not claim done when the gate is unmet'
Assert-True ($completionGate -match 'instead of claiming done') 'core-lead must report incomplete instead of claiming done'
Assert-True ($completionGate -match 're-verify before completion') 'core-lead must re-verify resolved findings before completion'
# Polarity-aware: the copula is asserted, so negating the rule fails.
Assert-True ($completionGate -match [regex]::Escape('dispatch that fails, is denied, times out, or returns no result is a `verification_blocked` outcome')) 'core-lead must map an unavailable reviewer dispatch to verification_blocked'
Assert-True ($completionGate -match 'reviewer tool is unavailable') 'core-lead must block when the reviewer tool is unavailable before dispatch'
Assert-True ($completionGate -match 'Never treat an unperformed review as a passed review') 'core-lead must never treat an unperformed review as passed'
Assert-True ($completionGate -match [regex]::Escape('never record a required review as "not required"')) 'core-lead must not allow a required review to be recorded as not required'

$reviewSection = Get-Flat (Get-Section $coreLead 'Review')
Assert-True ($reviewSection.Length -gt 0) 'core-lead must define a Review section'
Assert-True ($coreLead -match '(?m)^    reviewer: allow$') 'core-lead must keep reviewer task permission available'
foreach ($phrase in @('Build: review is required when a change touches two or more production files', 'Feature Freeze: review is required only when a change touches two or more production files and at least one', 'Demo Survival: review is required only when a change touches two or more production files and at least one', 'Production files are tracked files outside tests, documentation, fixtures, examples, and generated output', 'Runtime configuration and package manifests count as production', 'classify every changed file', 'record every risk flag as true or false with affected paths', 'demo_path', 'cross_module', 'concurrency', 'shared_state', 'external_api', 'external_integration', 'demo_blocking_cross_module_crash', 'review_not_required', '`reviewer` subagent', '`explorer` is not a substitute', 'not your judgment', 'authoritative for what they cover', 'not sufficient for completion', 'gets a regression test when the correction changes behavior')) {
  Assert-True ($reviewSection -match [regex]::Escape($phrase)) "core-lead Review must state '$phrase'"
}
Assert-True ($reviewSection -match [regex]::Escape('Feature Freeze: review is required only when a change touches two or more production files and at least one of these flags is true: `demo_path`, `cross_module`, `concurrency`, `shared_state`, or `external_api`')) 'core-lead must preserve the exact Feature Freeze risk mapping'
Assert-True ($reviewSection -match [regex]::Escape('Demo Survival: review is required only when a change touches two or more production files and at least one of these flags is true: `concurrency`, `shared_state`, `external_integration`, or `demo_blocking_cross_module_crash`')) 'core-lead must preserve the exact Demo Survival risk mapping'
$deadlineSection = Get-Flat (Get-Section $coreLead 'Deadline awareness')
Assert-True ($deadlineSection -match [regex]::Escape('Never invent a deadline; with none stated, use Build discipline and say so')) 'core-lead must default to Build when no deadline is supplied'

$realPathEvidence = Get-Flat (Get-Section $coreLead 'Real-path evidence')
Assert-True ($realPathEvidence.Length -gt 0) 'core-lead must define a Real-path evidence section'
Assert-True ($realPathEvidence -match [regex]::Escape('Do not use a mocked clock, a synthetic counter, implementation internals, or a self-authored substitute metric as evidence')) 'core-lead must prohibit substitute metrics as real-world evidence'
foreach ($phrase in @('real command, API, or execution path', 'substitute metric', 'fixture or input size', 'threshold', 'observed value', 'exit code')) {
  Assert-True ($realPathEvidence -match [regex]::Escape($phrase)) "core-lead Real-path evidence must mention '$phrase'"
}

$coreBehavior = Get-Flat (Get-Section (Read-Text 'AGENTS.md') 'Core behavior')
Assert-True ($coreBehavior.Length -gt 0) 'AGENTS.md must define a Core behavior section'
foreach ($phrase in @('completion receipt', 'verification_blocked', 'deadline mode', 'Feature Freeze', 'Demo Survival', 'demo_path', 'demo_blocking_cross_module_crash', 'Classify every changed file', '`explorer` is not a substitute')) {
  Assert-True ($coreBehavior -match [regex]::Escape($phrase)) "AGENTS.md Core behavior must state '$phrase'"
}

$readmeCore = Get-Flat (Get-Section (Read-Text 'README.md') 'Core 的行為')
Assert-True ($readmeCore -match [regex]::Escape('`explorer` 不可替代')) 'README Core behavior must forbid explorer substitution'
Assert-True ($readmeCore -match 'completion receipt') 'README Core behavior must document the completion receipt'
Assert-True ($readmeCore -match 'Demo Survival') 'README Core behavior must document the Demo Survival review gate'
Assert-True ($readmeCore -match 'demo_path') 'README Core behavior must name the Feature Freeze risk flags'
Assert-True ($readmeCore -match 'demo_blocking_cross_module_crash') 'README Core behavior must name the Demo Survival risk flags'

$reviewerBlockedSmoke = Read-Text 'scripts\smoke-core-reviewer-blocked.ps1'
foreach ($phrase in @('[IO.Path]::GetTempPath()', 'reviewer: allow', 'reviewer: deny', 'OPENCODE_CONFIG_DIR', 'Remove-Item Env:OPENCODE_CONFIG_CONTENT', 'Remove-Item Env:OPENCODE_DISABLE_DEFAULT_PLUGINS', '--pure', '--auto', 'verification_blocked', 'CORE_REVIEWER_BLOCKED_SMOKE_PASS', 'CORE_REVIEWER_BLOCKED_SELFTEST_PASS', 'final_answer', 'TaskEvents', 'NestedOpenCodeCommands', 'positive completion claim', '-SelfTest', 'finally', 'two or more production files')) {
  Assert-True ($reviewerBlockedSmoke -match [regex]::Escape($phrase)) "reviewer-blocked smoke must state '$phrase'"
}
$smokeSelfTestOutput = & pwsh -NoProfile -File (Join-Path $Root 'scripts\smoke-core-reviewer-blocked.ps1') -SelfTest 2>&1 | Out-String
Assert-True ($LASTEXITCODE -eq 0) "reviewer-blocked offline self-test must exit 0: $smokeSelfTestOutput"
Assert-True ($smokeSelfTestOutput -match 'CORE_REVIEWER_BLOCKED_SELFTEST_PASS') 'reviewer-blocked offline self-test must pass'

# --- Launchers and Desktop wrappers ------------------------------------------

foreach ($script in @(
    'scripts\oc-vanilla.ps1', 'scripts\oc-stable.ps1', 'scripts\oc-core.ps1', 'scripts\oc-core-codegraph.ps1',
    'scripts\oc-vanilla.sh', 'scripts\oc-stable.sh', 'scripts\oc-core.sh',
    'scripts\desktop-vanilla.ps1', 'scripts\desktop-core.ps1',
    'scripts\opencode-desktop-common.ps1', 'scripts\verify-modes.ps1')) {
  Assert-True (Test-Path -LiteralPath (Join-Path $Root $script)) "missing $script"
}

$coreLauncher = Read-Text 'scripts\oc-core.ps1'
Assert-True ($coreLauncher -match '--pure') 'Core launcher must run OpenCode in pure mode'
Assert-True ($coreLauncher -match 'XDG_CONFIG_HOME') 'Core launcher must isolate XDG_CONFIG_HOME'
Assert-True ($coreLauncher -match 'OPENCODE_CONFIG_DIR') 'Core launcher must isolate OPENCODE_CONFIG_DIR'
Assert-True ($coreLauncher -match 'OPENCODE_DISABLE_EXTERNAL_SKILLS') 'Core launcher must disable external skills'
Assert-CoreClearsDefaultPlugins $coreLauncher 'Core launcher'

$codeGraphLauncher = Read-Text 'scripts\oc-core-codegraph.ps1'
$codeGraphInstaller = Read-Text 'scripts\install-codegraph-windows.ps1'
foreach ($hash in @(
    'aa1b6108217c119af6ac444b8652a0eadcfe2c343bff78ead2edd15b6b7b15b1',
    '52f8ebe8f08f369a44fed6d1cb680c7c89169795e1c2949ee25b88b538ef0948')) {
  Assert-True ($codeGraphLauncher -match $hash) "CodeGraph launcher must enforce pinned hash $hash"
  Assert-True ($codeGraphInstaller -match $hash) "CodeGraph installer and launcher must share pinned hash $hash"
}
Assert-CoreClearsDefaultPlugins $codeGraphLauncher 'Core CodeGraph launcher'

$canaryRoot = Join-Path ([IO.Path]::GetTempPath()) ("opencode-codegraph-launcher-test-" + [guid]::NewGuid().ToString('N'))
$originalUserProfile = $env:USERPROFILE
try {
  $canaryMode = Join-Path $canaryRoot '.config\opencode\modes\core'
  New-Item -ItemType Directory -Force -Path (Join-Path $canaryMode 'skills\test-driven-development') | Out-Null
  [IO.File]::WriteAllText((Join-Path $canaryMode 'opencode-codegraph.jsonc'), '{}')
  $env:USERPROFILE = $canaryRoot
  $missingOutput = & pwsh -NoProfile -File (Join-Path $Root 'scripts\oc-core-codegraph.ps1') 2>&1 | Out-String
  Assert-True ($LASTEXITCODE -ne 0 -and $missingOutput -match 'Pinned CodeGraph 0\.20\.1 is missing') 'CodeGraph launcher must fail clearly when the pinned binary is missing'

  $fakeEngineDir = Join-Path $canaryRoot '.codegraph\bin\v0.20.1'
  New-Item -ItemType Directory -Force -Path $fakeEngineDir | Out-Null
  [IO.File]::WriteAllText((Join-Path $fakeEngineDir 'codegraph-server-win32-x64.exe'), 'tampered')
  [IO.File]::WriteAllText((Join-Path $fakeEngineDir 'onnxruntime.dll'), 'tampered')
  $tamperedOutput = & pwsh -NoProfile -File (Join-Path $Root 'scripts\oc-core-codegraph.ps1') 2>&1 | Out-String
  Assert-True ($LASTEXITCODE -ne 0 -and $tamperedOutput -match 'checksum mismatch') 'CodeGraph launcher must fail clearly when the pinned binary is tampered'
} finally {
  $env:USERPROFILE = $originalUserProfile
  if (Test-Path -LiteralPath $canaryRoot) { Remove-Item -LiteralPath $canaryRoot -Recurse -Force }
}

$coreLauncherSh = Read-Text 'scripts\oc-core.sh'
Assert-True ($coreLauncherSh -match '--pure') 'Core shell launcher must run OpenCode in pure mode'
Assert-True ($coreLauncherSh -match 'OPENCODE_CONFIG_DIR') 'Core shell launcher must isolate OPENCODE_CONFIG_DIR'
Assert-True ($coreLauncherSh -match 'OPENCODE_DISABLE_EXTERNAL_SKILLS') 'Core shell launcher must disable external skills'
Assert-CoreClearsDefaultPlugins $coreLauncherSh 'Core shell launcher'

$vanillaLauncher = Read-Text 'scripts\oc-vanilla.ps1'
Assert-True ($vanillaLauncher -notmatch '--pure') 'Vanilla launcher must not use pure mode'
Assert-True ($vanillaLauncher -notmatch 'XDG_CONFIG_HOME') 'Vanilla launcher must not isolate XDG_CONFIG_HOME'

# Vanilla and Stable must clear an inherited OPENCODE_DISABLE_DEFAULT_PLUGINS so
# the built-in provider plugins stay enabled for the pinned model. Only the Core
# entry points were covered before.
foreach ($entry in @(
    'scripts\oc-vanilla.ps1', 'scripts\oc-vanilla.sh',
    'scripts\oc-stable.ps1', 'scripts\oc-stable.sh',
    'scripts\desktop-vanilla.ps1')) {
  Assert-CoreClearsDefaultPlugins (Read-Text $entry) $entry
}

$desktopCore = Read-Text 'scripts\desktop-core.ps1'
$desktopVanilla = Read-Text 'scripts\desktop-vanilla.ps1'
Assert-True ($desktopCore -match 'desktop-core') 'Core Desktop wrapper must use its own user-data directory'
Assert-True ($desktopVanilla -match 'desktop-vanilla') 'Vanilla Desktop wrapper must use its own user-data directory'
Assert-True ($desktopCore -match 'XDG_CONFIG_HOME') 'Core Desktop wrapper must isolate XDG_CONFIG_HOME'
Assert-True ($desktopCore -match 'OPENCODE_CONFIG_DIR') 'Core Desktop wrapper must isolate OPENCODE_CONFIG_DIR'
Assert-True ($desktopCore -match 'OPENCODE_DISABLE_EXTERNAL_SKILLS') 'Core Desktop wrapper must disable external skills'
Assert-CoreClearsDefaultPlugins $desktopCore 'Core Desktop wrapper'
# The Desktop app is Electron and does not forward --pure to its OpenCode sidecar,
# so Desktop Core isolates through its own OPENCODE_CONFIG_DIR, XDG_CONFIG_HOME,
# and OPENCODE_DISABLE_EXTERNAL_SKILLS; --pure is required only of the two CLI Core
# launchers. Guard against reintroducing --pure here, where it does nothing.
Assert-True ($desktopCore -notmatch '--pure') 'Core Desktop wrapper must not rely on --pure: Electron does not forward it, so Desktop isolation rests on OPENCODE_CONFIG_DIR, XDG_CONFIG_HOME, and OPENCODE_DISABLE_EXTERNAL_SKILLS'
Assert-True ($desktopVanilla -notmatch 'XDG_CONFIG_HOME') 'Vanilla Desktop wrapper must not isolate XDG_CONFIG_HOME'
Assert-True ($desktopCore -match 'user-data-dir') 'Core Desktop wrapper must pass --user-data-dir'
Assert-True ($desktopVanilla -match 'user-data-dir') 'Vanilla Desktop wrapper must pass --user-data-dir'

# --- Setup scripts ------------------------------------------------------------

$setupWin = Read-Text 'scripts\setup-windows.ps1'
$setupUnix = Read-Text 'scripts\setup-unix.sh'
foreach ($setup in @(@('windows', $setupWin), @('unix', $setupUnix))) {
  $name = $setup[0]; $content = $setup[1]
  Assert-True ($content -match '6\.3\.0') "$name setup must require the tested Superpowers version"
  Assert-True ($content -match 'modes') "$name setup must deploy mode directories"
  Assert-True ($content -match 'core-lead\.md') "$name setup must deploy the Core lead"
  Assert-True ($content -match 'finishing-a-development-branch') "$name setup must deploy the Core skill list"
  Assert-True ($content -match 'manifest\.json') "$name setup must record a Core skill manifest"
  Assert-True ($content -notmatch '(?i)mattpocock/skills') "$name setup must not install Matt skills"
  Assert-True ($content -notmatch 'ensemble\.json\.template') "$name setup must not install an Ensemble template"
  Assert-True ($content -match 'team-lead\.md') "$name setup must list the retired team-lead agent for cleanup"
  Assert-True ($content -match 'ensemble\.json') "$name setup must list the retired Ensemble config for cleanup"
  Assert-True ($content -match 'oc-product') "$name setup must list the retired oc-product wrapper for cleanup"
}
Assert-True ($setupWin -match 'CleanLegacy') 'Windows setup must offer the legacy cleanup switch'
Assert-True ($setupUnix -match '--clean-legacy') 'Unix setup must offer the legacy cleanup flag'
Assert-True ($setupWin -match 'OpenCode Vanilla') 'Windows setup must create the Vanilla Desktop shortcut'
Assert-True ($setupWin -match 'OpenCode Core') 'Windows setup must create the Core Desktop shortcut'
Assert-True ($setupWin -match 'the stock OpenCode shortcut was not modified') 'Windows setup must leave the stock shortcut alone'
Assert-True ($setupWin -match 'oc-vanilla') 'Windows setup must install the Vanilla CLI launcher'
Assert-True ($setupWin -match 'oc-stable') 'Windows setup must install the Stable CLI launcher'
Assert-True ($setupWin -match 'oc-core') 'Windows setup must install the Core CLI launcher'
# A fresh machine must get a global config, or the stock shortcut has no plugin
# and no default agent.
Assert-True ($setupWin -match 'global\\opencode.jsonc') 'Windows setup must install the portable global config when missing'
Assert-True ($setupUnix -match 'global/opencode.jsonc') 'Unix setup must install the portable global config when missing'
# gstack routing is shared and portable, so a fresh machine must get the config and
# an existing one must be left untouched. Read the install block itself, so deleting
# it fails the suite instead of leaving a bare path string behind.
$unixGstackBlock = [regex]::Match($setupUnix, '(?s)# gstack routing is shared.*?\nfi').Value
Assert-True ($unixGstackBlock.Length -gt 0) 'Unix setup must define a gstack config installation block'
Assert-True ($unixGstackBlock -match '\[\[ ! -e "\$GSTACK_CONFIG" \]\]') 'Unix setup must install gstack.jsonc only when it is missing'
Assert-True ($unixGstackBlock -match 'cp "\$ROOT/gstack/gstack\.jsonc" "\$GSTACK_CONFIG"') 'Unix setup must copy the portable gstack.jsonc when missing'
Assert-True ($unixGstackBlock -match 'left untouched') 'Unix setup must leave an existing gstack.jsonc untouched'
Assert-True ($setupWin -match 'Copy-Item \(Join-Path \$RepoRoot ''gstack\\gstack\.jsonc''\)') 'Windows setup must install the portable gstack config when missing'
Assert-True ($setupWin -match 'gstack\.jsonc exists; left untouched') 'Windows setup must leave an existing gstack.jsonc untouched'
# The backup must cover the launchers and the shortcuts this repo owns. Matching
# the bare string "oc-*.cmd" is not evidence: the old code passed the wildcard to
# -LiteralPath and swallowed the resulting failure, so nothing was copied. Read the
# actual backup blocks and require wildcard-expanding copies that surface errors.
$modesBackupBlock = [regex]::Match($setupWin, '(?s)\$modesSource = Join-Path \$OcConfig ''modes''.*?(?=\$coreSource)').Value
Assert-True ($modesBackupBlock.Length -gt 0) 'Windows setup must back up the mode launcher scripts'
Assert-True ($modesBackupBlock -match 'Get-ChildItem -Path \(Join-Path \$modesSource ''\*\.ps1''\)') 'Windows setup must enumerate the mode *.ps1 scripts for backup'
Assert-True ($modesBackupBlock -match 'Copy-Item -LiteralPath \$modeScript\.FullName') 'Windows setup must copy each enumerated mode *.ps1 script'
Assert-True ($modesBackupBlock -notmatch 'Copy-Item -LiteralPath[^\r\n]*\*') 'Windows setup must not pass a wildcard to -LiteralPath for the *.ps1 backup'
Assert-True ($modesBackupBlock -notmatch 'SilentlyContinue') 'Windows setup must not swallow mode *.ps1 backup failures'

$shimBackupBlock = [regex]::Match($setupWin, '(?s)# CLI shims and the two mode shortcuts this repository owns\..*?(?=\r?\nforeach \(\$desktop)').Value
Assert-True ($shimBackupBlock.Length -gt 0) 'Windows setup must back up the CLI shims'
Assert-True ($shimBackupBlock -match 'Get-ChildItem -Path \(Join-Path \$binSource ''oc-\*\.cmd''\)') 'Windows setup must enumerate the oc-*.cmd shims for backup'
Assert-True ($shimBackupBlock -match 'Copy-Item -LiteralPath \$shim\.FullName') 'Windows setup must copy each enumerated oc-*.cmd shim'
Assert-True ($shimBackupBlock -notmatch 'Copy-Item -LiteralPath[^\r\n]*\*') 'Windows setup must not pass a wildcard to -LiteralPath for the shim backup'
Assert-True ($shimBackupBlock -notmatch 'SilentlyContinue') 'Windows setup must not swallow shim backup failures'
Assert-True ($setupWin -match 'OpenCode Vanilla') 'Windows setup must reference the managed shortcuts for backup and cleanup'
# Real safety check: the stock OpenCode shortcut must be absent from the deletion
# list. The Write-Host string above is not evidence; this reads the list itself.
$legacyFilesBlock = [regex]::Match($setupWin, '(?s)\$LegacyFiles = @\(.*?\n\)').Value
Assert-True ($legacyFilesBlock.Length -gt 0) 'Windows setup must define a retired-artifact deletion list'
Assert-True ($legacyFilesBlock -notmatch 'OpenCode\.lnk') 'the stock OpenCode shortcut must not be in the deletion list'
$legacyShortcutBlock = [regex]::Match($setupWin, '(?s)# Shortcuts created by the retired two-mode design.*?\n\}').Value
Assert-True ($legacyShortcutBlock.Length -gt 0) 'Windows setup must build the retired-shortcut deletion list'
Assert-True ($legacyShortcutBlock -notmatch "'OpenCode'") 'the stock OpenCode shortcut must not be a deletion label'
Assert-True ($legacyShortcutBlock -match 'OpenCode PRODUCT') 'the retired PRODUCT shortcut must stay in the deletion list'
Assert-True ($legacyShortcutBlock -match 'OpenCode TEAM') 'the retired TEAM shortcut must stay in the deletion list'
Assert-True ($setupUnix -notmatch '\.lnk') 'Unix setup must not reference or delete any shortcut'
# Version handling must compare against the 6.3.0 pin and fail loudly, never
# silently fall back to the full plugin.
Assert-True ($setupWin -match '\$version -ne \$RequiredSuperpowersVersion') 'Windows setup must compare the discovered version against the 6.3.0 pin'
Assert-True ($setupWin -match 'throw "Superpowers \$version found but \$RequiredSuperpowersVersion is required') 'Windows setup must fail explicitly on a Superpowers version mismatch'
Assert-True ($setupWin -notmatch '(?i)fall\s?back') 'Windows setup must not silently fall back to the full plugin'
Assert-True ($setupUnix -match 'VERSION.*REQUIRED_SUPERPOWERS_VERSION') 'Unix setup must compare the discovered version against the 6.3.0 pin'
Assert-True ($setupUnix -match 'is required') 'Unix setup must fail loudly on a Superpowers version mismatch'
Assert-True ($setupUnix -notmatch '(?i)fall\s?back') 'Unix setup must not silently fall back to the full plugin'

# --- Shared global configuration and workers ---------------------------------

$global = Read-Json 'global\opencode.jsonc'
Assert-True ($global.default_agent -eq 'stable-lead') 'the stock global config must default to stable-lead'
Assert-True (@($global.plugin) -contains $superpowersSpec) 'the stock global config must load Superpowers'
Assert-True ((Read-Text 'global\opencode.jsonc') -notmatch 'opencode-ensemble') 'the stock global config must not reference Ensemble'

$secretPaths = @(
  '**/.env', '**/.env.*', '**/secrets/**', '**/credentials/**',
  '**/*credentials*', '**/*secret*', '**/*.pem', '**/*.key',
  '**/id_rsa', '**/id_ed25519'
)
$workers = @{
  explorer = Read-Text 'agents\explorer.md'
  implementer = Read-Text 'agents\implementer.md'
  reviewer = Read-Text 'agents\reviewer.md'
  'test-writer' = Read-Text 'agents\test-writer.md'
}
foreach ($worker in $workers.GetEnumerator()) {
  $name = $worker.Key; $content = $worker.Value
  Assert-True ($content -match '(?m)^model: deepseek/deepseek-v4-flash\s*$') "$name must route to the DeepSeek worker model"
  Assert-True ((Get-Body $content) -notmatch $legacyWorkflow) "$name body must not reference any retired workflow"
  Assert-True ($content -match '(?m)^  task: deny\s*$') "$name must not spawn subagents"
  Assert-True ($content -match '(?m)^  webfetch: deny\s*$') "$name must not reach the web"
  $readSection = Get-PermissionSection $content 'read'
  Assert-True (([regex]::Matches($readSection, '":\s*deny')).Count -eq $secretPaths.Count) "$name read section must contain exactly the secret denials"
}
foreach ($readOnly in @('explorer', 'reviewer')) {
  Assert-True ($workers[$readOnly] -match '(?m)^  edit: deny\s*$') "$readOnly must be read-only"
}
Assert-True ($workers['implementer'] -match '(?m)^## Completion handback\s*$') 'implementer must use the exact Completion handback heading'

# Restore the worker assertions dropped in the refactor: the rules still exist in
# the agent files, but nothing would catch future drift.
$implementer = $workers['implementer']
foreach ($denial in @('git push*', 'git commit*', 'git merge*', 'git rebase*', 'git reset --hard*', 'git clean*', 'git branch -D*', 'rm -rf*')) {
  Assert-True ($implementer -match ('(?m)^    "' + [regex]::Escape($denial) + '": deny\s*$')) "implementer must deny the bash command $denial"
}
foreach ($bullet in @('- Changed files', '- Commands run and exact result', '- Core acceptance result', '- Remaining limitation or blocker')) {
  Assert-True ($implementer -match ('(?m)^' + [regex]::Escape($bullet) + '\s*$')) "implementer handback must include '$bullet'"
}
$testWriterEdit = Get-PermissionSection $workers['test-writer'] 'edit'
Assert-True ($testWriterEdit -match '(?m)^    "\*": deny\s*$') 'test-writer edit section must deny by default'
Assert-True ($testWriterEdit -match '(?m)^    "\*\*/tests/\*\*": allow\s*$') 'test-writer edit section must allow **/tests/**'

# The binding requirement denies credential paths in every agent, including both
# primary agents. Only the four workers were covered before.
foreach ($primary in @(
    @('stable-lead', (Read-Text 'agents\stable-lead.md')),
    @('core-lead', (Read-Text 'modes\core\agents\core-lead.md')))) {
  $primaryName = $primary[0]; $primaryContent = $primary[1]
  $primaryRead = Get-PermissionSection $primaryContent 'read'
  Assert-True (([regex]::Matches($primaryRead, '":\s*deny')).Count -eq $secretPaths.Count) "$primaryName read section must contain exactly the secret denials"
}

# --- Documentation ------------------------------------------------------------

$readme = Read-Text 'README.md'
Assert-True ($readme -match 'Vanilla') 'README must document the Vanilla mode'
Assert-True ($readme -match 'Stable') 'README must document the Stable mode'
Assert-True ($readme -match 'Core') 'README must document the Core mode'
Assert-True ($readme -match 'oc-core') 'README must document the Core launcher'
Assert-True ($readme -match 'oc-vanilla') 'README must document the Vanilla launcher'
Assert-True ($readme -match 'oc-stable') 'README must document the Stable launcher'

$agentsDoc = Read-Text 'AGENTS.md'
Assert-True ($agentsDoc -match 'Vanilla') 'AGENTS.md must describe the three modes'
Assert-True ($agentsDoc -match 'Core') 'AGENTS.md must describe the Core mode'

$spec = Read-Text 'docs\superpowers\specs\2026-09-19-three-mode-opencode-workflows-design.md'
Assert-True ($spec -match 'Three-Mode OpenCode Workflows Design') 'the three-mode design spec must exist'
Assert-True ($spec -match 'Verified limitation: one Desktop instance at a time') 'the spec must record the verified Desktop single-instance limitation'
Assert-True ($spec -match 'deadline-aware read-only reviewer gate') 'the spec must record the deadline-aware Core reviewer gate'

# Regression guard: the design must not re-claim concurrent Desktop instances.
$readmeText = Read-Text 'README.md'
Assert-True ($readmeText -match '一次只能開一個實例') 'README must document the Desktop single-instance limitation'
Assert-True ($readmeText -notmatch '可以\*\*同時開啟\*\*') 'README must not claim concurrent Desktop instances'
Assert-True ((Read-Text 'desktop\opencode\README.md') -match 'only one Desktop instance at a time') 'desktop README must document the Desktop single-instance limitation'

'THREE_MODE_ACCEPTANCE_PASS'
