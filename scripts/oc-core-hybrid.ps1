<#
.SYNOPSIS
    Static-routing Core launcher (Stage 0, dry-run friendly).

.DESCRIPTION
    Builds a routing state from a request file and a repository, asks the
    deterministic static router which execution tier the task belongs to, and
    either prints the decision (-DryRun) or launches OpenCode with the model
    that tier selects.

    This script never writes to the OpenCode configuration. It reads the
    deployed Core mode and sets environment variables for the child process,
    restoring the caller's values when the child exits; nothing on disk has
    changed and nothing leaks into the calling session. Tests enforce both.

    The request is supplied as a file rather than typed into a session. That is
    deliberate: routing has to happen before OpenCode starts. A daily-use entry
    point would need a session hook, which
    docs/research/2026-09-19-jev-risk-routed-hybrid-core.md section 18 flags as
    unsafe on OpenCode 1.18.31. Treat this as a measurement tool, not the daily
    entry point.

.PARAMETER RequestFile
    Path to the request text.

.PARAMETER RepoRoot
    Repository the task will touch. Used to derive candidate paths and to detect
    how the repository runs its tests.

.PARAMETER TierB
    Which reading of section 6's "clearly specified" to use for the Guarded
    tier. 'conservative' refuses to promote a task whose scope is unknown.

.PARAMETER DryRun
    Print the decision and exit. Launches nothing and touches nothing.

.EXAMPLE
    .\scripts\oc-core-hybrid.ps1 -RequestFile .\req.md -RepoRoot . -DryRun
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RequestFile,
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [ValidateSet('conservative', 'broad')][string]$TierB = 'conservative',
    [switch]$DryRun,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest
)

$ErrorActionPreference = 'Stop'

$KitRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'python is not on PATH; the router needs it.'
}
if (-not (Test-Path -LiteralPath $RequestFile)) {
    throw "Request file not found: $RequestFile"
}

# Ask the router. PYTHONPATH is scoped to this call and restored afterwards.
$previousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = if ($previousPythonPath) { "$KitRoot;$previousPythonPath" } else { $KitRoot }
try {
    $raw = & python -m router.cli --request-file $RequestFile --repo $RepoRoot --tier-b $TierB --json
    $routerExit = $LASTEXITCODE
}
finally {
    $env:PYTHONPATH = $previousPythonPath
}
if ($routerExit -ne 0) { throw "router exited $routerExit" }

$decision = $raw | ConvertFrom-Json
Write-Host "ROUTE tier=$($decision.tier) model=$($decision.model)"
Write-Host "      reason: $($decision.reason)"

if ($DryRun) {
    Write-Host 'DRY RUN: nothing was launched and no configuration was touched.'
    exit 0
}

$coreMode = Join-Path $env:USERPROFILE '.config\opencode\modes\core'
$config = Join-Path $coreMode 'opencode.jsonc'
if (-not (Test-Path -LiteralPath $config)) {
    throw "Core mode is not deployed at $coreMode. Run scripts/setup-windows.ps1 first."
}

# The request is also the prompt: routing and execution must see the same text,
# or the measurement would not describe what actually ran.
$prompt = [IO.File]::ReadAllText($RequestFile)

# The same isolation the existing Core launcher uses. A script invoked with `&`
# shares the caller's process, so every variable touched here is snapshotted and
# restored afterwards; otherwise the next plain `opencode` in that terminal would
# silently run the Core configuration.
$isolationNames = @(
    'OPENCODE_CONFIG',
    'OPENCODE_CONFIG_DIR',
    'XDG_CONFIG_HOME',
    'OPENCODE_DISABLE_EXTERNAL_SKILLS',
    'OPENCODE_CONFIG_CONTENT',
    'OPENCODE_DISABLE_DEFAULT_PLUGINS'
)
$callerEnvironment = @{}
foreach ($name in $isolationNames) {
    $callerEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

Push-Location -LiteralPath $RepoRoot
try {
    $env:OPENCODE_CONFIG = $config
    $env:OPENCODE_CONFIG_DIR = $coreMode
    $env:XDG_CONFIG_HOME = Join-Path $coreMode 'xdg'
    $env:OPENCODE_DISABLE_EXTERNAL_SKILLS = '1'
    Remove-Item Env:OPENCODE_CONFIG_CONTENT -ErrorAction SilentlyContinue
    Remove-Item Env:OPENCODE_DISABLE_DEFAULT_PLUGINS -ErrorAction SilentlyContinue

    & opencode --pure --model $decision.model run --format json --agent core-lead --auto $prompt @Rest
    $openCodeExit = $LASTEXITCODE
}
finally {
    Pop-Location
    # Unset values are deleted, not assigned: PowerShell passes $null to .NET as '', and
    # recent .NET keeps an empty variable defined instead of deleting it.
    foreach ($name in $isolationNames) {
        if ($null -eq $callerEnvironment[$name]) { Remove-Item Env:$name -ErrorAction SilentlyContinue }
        else { [Environment]::SetEnvironmentVariable($name, $callerEnvironment[$name], 'Process') }
    }
}
exit $openCodeExit
