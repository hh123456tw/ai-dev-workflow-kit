# Claude lane launcher. Deployed by scripts/setup-claude-lane.ps1 next to the
# `core` directory it loads; invoked by the claude-core / claude-ds shims.
#
#   claude-lane.ps1 core [claude args...]   Max subscription through the official CLI
#   claude-lane.ps1 ds   [claude args...]   DeepSeek through its Anthropic-compatible API
#
# Both lanes load the same Core rules, curated skills, read-only agents, and
# completion gate. No param block on purpose: every argument after the lane goes
# to `claude` untouched, including short flags such as -p.
#
# Isolation is environment-only and scoped to this launch. Every variable touched
# is restored afterwards, because a script invoked with `&` shares the caller's
# process. Persistent ANTHROPIC_* overrides (for example a leftover
# ANTHROPIC_DEFAULT_SONNET_MODEL pointing at another vendor) are removed for the
# child so the lane runs the backend it names, never a silent substitute.
$ErrorActionPreference = 'Stop'

function Stop-Lane([string]$message) {
  [Console]::Error.WriteLine("claude-lane: $message")
  exit 2
}

$lane = if ($args.Count -gt 0) { [string]$args[0] } else { '' }
if ($lane -ne 'core' -and $lane -ne 'ds') {
  Stop-Lane 'usage: claude-lane.ps1 core|ds [claude arguments...]'
}
$claudeArgs = @()
if ($args.Count -gt 1) { $claudeArgs = @($args[1..($args.Count - 1)]) }

$kitHome = $PSScriptRoot
$mode = Join-Path $kitHome 'core'
$plugin = Join-Path $mode 'plugin'
$rules = Join-Path $mode 'CORE.md'
$settingsPath = Join-Path $mode 'settings.json'
$manifestPath = Join-Path $plugin 'skills\manifest.json'
foreach ($required in @($rules, $settingsPath, (Join-Path $plugin '.claude-plugin\plugin.json'), $manifestPath)) {
  if (-not (Test-Path -LiteralPath $required)) {
    Stop-Lane "Claude lane is not deployed at $kitHome ($required missing). Run scripts/setup-claude-lane.ps1."
  }
}
# The completion gate is a hook; a hook whose interpreter is missing fails open.
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if (-not $manifest.python -or -not (Test-Path -LiteralPath $manifest.python)) {
  Stop-Lane "The completion gate interpreter '$($manifest.python)' is missing. Re-run scripts/setup-claude-lane.ps1."
}
if (-not (Get-Command claude -CommandType Application, Function -ErrorAction SilentlyContinue)) {
  Stop-Lane 'claude is not on PATH. Install Claude Code first.'
}

$deepseekKey = $env:DEEPSEEK_API_KEY
if ($lane -eq 'ds' -and [string]::IsNullOrEmpty($deepseekKey)) {
  Stop-Lane 'claude-ds needs DEEPSEEK_API_KEY in the environment. It never falls back to the Max subscription.'
}

# Hide personal skills so the lane exposes exactly the six curated ones.
$skillsHome = if ($lane -eq 'ds') { Join-Path $kitHome 'ds-home\skills' } else { Join-Path $env:USERPROFILE '.claude\skills' }
$overrides = [ordered]@{}
if (Test-Path -LiteralPath $skillsHome) {
  foreach ($skill in Get-ChildItem -LiteralPath $skillsHome -Directory) { $overrides[$skill.Name] = 'off' }
}
$settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
$settings | Add-Member -NotePropertyName skillOverrides -NotePropertyValue ([pscustomobject]$overrides) -Force
$sessionSettings = Join-Path ([IO.Path]::GetTempPath()) ("claude-lane-" + [guid]::NewGuid().ToString('N') + '.json')
[IO.File]::WriteAllText($sessionSettings, ($settings | ConvertTo-Json -Depth 10))

$managed = @(Get-ChildItem Env: | Where-Object { $_.Name -like 'ANTHROPIC_*' } | ForEach-Object { $_.Name })
$managed += @(
  'CLAUDE_CONFIG_DIR', 'CLAUDE_CODE_SUBAGENT_MODEL', 'CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_USE_VERTEX',
  'CLAUDE_CODE_USE_FOUNDRY', 'CLAUDE_CODE_EFFORT_LEVEL', 'CLAUDE_CODE_AUTO_COMPACT_WINDOW',
  'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC', 'CLAUDE_CODE_SUBPROCESS_ENV_SCRUB',
  'ANTHROPIC_BASE_URL', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_MODEL', 'ANTHROPIC_DEFAULT_OPUS_MODEL',
  'ANTHROPIC_DEFAULT_SONNET_MODEL', 'ANTHROPIC_DEFAULT_HAIKU_MODEL'
)
# Launched from inside another Claude Code session (Desktop, SDK), the child would
# inherit that host's session wiring and look for host-provided auth instead of
# its own login ("Not logged in"). The lane is always a standalone session.
$managed += @(
  'CLAUDECODE', 'CLAUDE_CODE_CHILD_SESSION', 'CLAUDE_CODE_ENTRYPOINT', 'CLAUDE_CODE_SDK_HAS_HOST_AUTH_REFRESH',
  'CLAUDE_CODE_OAUTH_SCOPES', 'CLAUDE_CODE_HOST_SESSION_ID', 'CLAUDE_CODE_SESSION_ID',
  'CLAUDE_CODE_MESSAGING_SOCKET', 'CLAUDE_CODE_MESSAGING_TOKEN', 'CLAUDE_AGENT_SDK_VERSION'
)
$managed += @('DEEPSEEK_API_KEY')
if ($lane -eq 'ds') { $managed += @('CLAUDE_CODE_OAUTH_TOKEN') }
$managed += @('CLAUDE_KIT_VERDICT_FILE')
$managed = @($managed | Select-Object -Unique)
$saved = @{}
foreach ($name in $managed) { $saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }

# The gate writes each Stop decision to this launch's own file. Reading it after
# the session means no git output to decode (Windows PowerShell garbles non-ASCII
# paths) and no verdict shared with another session in the same repository.
$verdictFile = Join-Path ([IO.Path]::GetTempPath()) ("claude-lane-verdict-" + [guid]::NewGuid().ToString('N') + '.json')
# Only a session reaches Stop; these invocations never produce a verdict.
$noSession = @('--version', '-v', '--help', '-h', 'auth', 'plugin', 'plugins', 'mcp', 'doctor', 'update',
  'install', 'config', 'setup-token', 'agents', 'migrate-installer')
# The subcommand is the first argument, or follows a boolean flag (`--debug mcp
# list`). Nothing else is skipped: in `--add-dir config "fix it"` the word
# `config` is a flag value, and in `-p update` it is the prompt.
$position = 0
while ($position -lt $claudeArgs.Count -and @('--debug', '-d', '--verbose') -contains [string]$claudeArgs[$position]) { $position++ }
$subcommand = if ($position -lt $claudeArgs.Count) { [string]$claudeArgs[$position] } else { '' }
$expectVerdict = -not (
  @($claudeArgs | Where-Object { @('--version', '-v', '--help', '-h') -contains [string]$_ }).Count -gt 0 -or
  $noSession -contains $subcommand
)

$exitCode = 1
try {
  # Remove-Item, not SetEnvironmentVariable($name, $null): PowerShell turns $null
  # into '' for .NET string parameters, and recent .NET keeps empty variables.
  foreach ($name in $managed) { Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue }
  $env:CLAUDE_KIT_VERDICT_FILE = $verdictFile
  if ($lane -eq 'ds') {
    # Scrubbing hides the DeepSeek key from the shell tool and hooks, but Claude
    # Code then forces the default permission mode and ignores a requested
    # bypassPermissions/acceptEdits. The chosen permission mode wins by default;
    # set CLAUDE_DS_SCRUB=1 to trade it for the key protection.
    if ($env:CLAUDE_DS_SCRUB -eq '1') { $env:CLAUDE_CODE_SUBPROCESS_ENV_SCRUB = '1' }
    $model = if ($env:CLAUDE_DS_MODEL) { $env:CLAUDE_DS_MODEL } else { 'deepseek-flash[1m]' }
    $small = if ($env:CLAUDE_DS_SMALL_MODEL) { $env:CLAUDE_DS_SMALL_MODEL } else { 'deepseek-flash' }
    # Separate config dir: no Max credentials exist there, so this lane cannot
    # spend the subscription even if the endpoint variables were lost.
    $env:CLAUDE_CONFIG_DIR = Join-Path $kitHome 'ds-home'
    $env:ANTHROPIC_BASE_URL = 'https://api.deepseek.com/anthropic'
    $env:ANTHROPIC_AUTH_TOKEN = $deepseekKey
    # Every alias is pinned: DeepSeek maps unpinned claude-opus names to the
    # pricier deepseek-v4-pro.
    $env:ANTHROPIC_MODEL = $model
    $env:ANTHROPIC_DEFAULT_OPUS_MODEL = $model
    $env:ANTHROPIC_DEFAULT_SONNET_MODEL = $model
    $env:ANTHROPIC_DEFAULT_HAIKU_MODEL = $small
    $env:CLAUDE_CODE_SUBAGENT_MODEL = $small
    $env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = '1'
  }
  $laneArgs = @(
    '--setting-sources', 'project,local',
    '--settings', $sessionSettings,
    '--plugin-dir', $plugin,
    '--append-system-prompt-file', $rules
  )
  & claude @laneArgs @claudeArgs
  $exitCode = $LASTEXITCODE
}
finally {
  foreach ($name in $managed) {
    if ($null -eq $saved[$name]) { Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue }
    else { Set-Item -LiteralPath "Env:$name" -Value $saved[$name] }
  }
  Remove-Item -LiteralPath $sessionSettings -Force -ErrorAction SilentlyContinue
}

# No verdict is a failure too: the gate crashed, timed out, could not start, or
# the session was interrupted before any Stop. Only an explicit OK passes.
$verdict = $null
if (Test-Path -LiteralPath $verdictFile) {
  try { $verdict = Get-Content -LiteralPath $verdictFile -Raw -Encoding UTF8 | ConvertFrom-Json } catch { $verdict = $null }
  Remove-Item -LiteralPath $verdictFile -Force -ErrorAction SilentlyContinue
}
if ($expectVerdict -and $exitCode -eq 0) {
  $ok = @('pass', 'no_changes', 'no_repository')
  if (-not $verdict) {
    [Console]::Error.WriteLine('claude-lane: COMPLETION GATE PRODUCED NO VERDICT (crashed, timed out, did not start, or the session was interrupted). Treat the task as NOT verified.')
    $exitCode = 3
  } elseif ($ok -notcontains [string]$verdict.verdict) {
    [Console]::Error.WriteLine("claude-lane: COMPLETION GATE $(([string]$verdict.verdict).ToUpper()). The task is NOT complete: $(@($verdict.problems) -join '; ')")
    $exitCode = 3
  }
}
exit $exitCode
