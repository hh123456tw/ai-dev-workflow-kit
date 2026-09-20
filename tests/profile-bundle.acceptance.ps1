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

# --- Launchers and Desktop wrappers ------------------------------------------

foreach ($script in @(
    'scripts\oc-vanilla.ps1', 'scripts\oc-stable.ps1', 'scripts\oc-core.ps1',
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

# Regression guard: the design must not re-claim concurrent Desktop instances.
$readmeText = Read-Text 'README.md'
Assert-True ($readmeText -match '一次只能開一個實例') 'README must document the Desktop single-instance limitation'
Assert-True ($readmeText -notmatch '可以\*\*同時開啟\*\*') 'README must not claim concurrent Desktop instances'
Assert-True ((Read-Text 'desktop\opencode\README.md') -match 'only one Desktop instance at a time') 'desktop README must document the Desktop single-instance limitation'

'THREE_MODE_ACCEPTANCE_PASS'
