<#
.SYNOPSIS
    Deploys the Claude lane (claude-core, claude-ds) of the Core mode.

.DESCRIPTION
    Copies modes/claude into -TargetRoot, fills the kit-core plugin with the six
    curated Core skills from the pinned Superpowers package, pins the completion
    gate to an absolute Python interpreter, validates the plugin with
    `claude plugin validate` when claude is installed, and writes the
    claude-core / claude-ds shims into -BinDir.

    It touches nothing under ~/.claude and never modifies OpenCode configuration.

.PARAMETER TargetRoot
    Deployment directory. Default: ~/.config/claude-kit.

.PARAMETER BinDir
    Where the .cmd shims go. Default: ~/bin (the directory the OpenCode shims use).

.PARAMETER SuperpowersPath
    Superpowers package root. Default: discovered under ~/.cache/opencode/packages.

.PARAMETER SkipShims
    Deploy without writing shims (used by tests).
#>
param(
  [string]$TargetRoot = (Join-Path $env:USERPROFILE '.config\claude-kit'),
  [string]$BinDir = (Join-Path $env:USERPROFILE 'bin'),
  [string]$SuperpowersPath = '',
  [switch]$SkipShims
)
$ErrorActionPreference = 'Stop'

$Repo = Split-Path -Parent $PSScriptRoot
$Source = Join-Path $Repo 'modes\claude'
$RequiredSuperpowersVersion = '6.3.0'
$CoreSkills = @(
  'test-driven-development',
  'systematic-debugging',
  'verification-before-completion',
  'requesting-code-review',
  'receiving-code-review',
  'finishing-a-development-branch'
)

function Find-Superpowers {
  $root = Join-Path $env:USERPROFILE '.cache\opencode\packages'
  if (-not (Test-Path -LiteralPath $root)) { return $null }
  foreach ($candidate in Get-ChildItem -LiteralPath $root -Directory -Recurse -Depth 6 -Filter 'superpowers' -ErrorAction SilentlyContinue) {
    $manifest = Join-Path $candidate.FullName 'package.json'
    if (-not (Test-Path -LiteralPath $manifest)) { continue }
    try {
      if ((Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json).version -eq $RequiredSuperpowersVersion) { return $candidate.FullName }
    } catch { }
  }
  return $null
}

Write-Host '[1/4] Locating Superpowers and Python...'
if (-not $SuperpowersPath) { $SuperpowersPath = Find-Superpowers }
if (-not $SuperpowersPath -or -not (Test-Path -LiteralPath (Join-Path $SuperpowersPath 'package.json'))) {
  throw "Superpowers $RequiredSuperpowersVersion not found. Launch OpenCode once in Stable, or pass -SuperpowersPath."
}
$version = (Get-Content -LiteralPath (Join-Path $SuperpowersPath 'package.json') -Raw | ConvertFrom-Json).version
if ($version -ne $RequiredSuperpowersVersion) {
  throw "Superpowers $version found but $RequiredSuperpowersVersion is required. Update the pin deliberately."
}
$python = Get-Command python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $python) { throw 'python is not on PATH; the completion gate needs it.' }
# Run it: the WindowsApps python.exe stub exists on disk but opens the Store.
# Collect all output first: Select-Object -First 1 would stop the native process
# early and leave $LASTEXITCODE undefined.
$probe = @(& $python.Source -c "import sys; print(sys.executable)" 2>$null)
$probeExit = $LASTEXITCODE
$pythonPath = if ($probe.Count -gt 0) { [string]$probe[0] } else { '' }
if ($probeExit -ne 0 -or -not $pythonPath -or -not (Test-Path -LiteralPath $pythonPath)) {
  throw "python at $($python.Source) does not run; install a real Python 3 and re-run."
}
Write-Host "  Superpowers $version at $SuperpowersPath; python at $pythonPath"

Write-Host "[2/4] Deploying to $TargetRoot..."
New-Item -ItemType Directory -Force -Path $TargetRoot | Out-Null
$coreTarget = Join-Path $TargetRoot 'core'
if (Test-Path -LiteralPath $coreTarget) { Remove-Item -LiteralPath $coreTarget -Recurse -Force }
Copy-Item -LiteralPath (Join-Path $Source 'core') -Destination $coreTarget -Recurse -Force
Copy-Item -LiteralPath (Join-Path $Source 'claude-lane.ps1') -Destination (Join-Path $TargetRoot 'claude-lane.ps1') -Force
Get-ChildItem -LiteralPath $coreTarget -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
New-Item -ItemType Directory -Force -Path (Join-Path $TargetRoot 'ds-home') | Out-Null

$pluginTarget = Join-Path $coreTarget 'plugin'
$skillsTarget = Join-Path $pluginTarget 'skills'
New-Item -ItemType Directory -Force -Path $skillsTarget | Out-Null
foreach ($skill in $CoreSkills) {
  $skillSource = Join-Path $SuperpowersPath "skills\$skill"
  if (-not (Test-Path -LiteralPath (Join-Path $skillSource 'SKILL.md'))) { throw "Core skill missing from Superpowers: $skill" }
  Copy-Item -LiteralPath $skillSource -Destination (Join-Path $skillsTarget $skill) -Recurse -Force
}
[IO.File]::WriteAllText((Join-Path $skillsTarget 'manifest.json'), ([ordered]@{
  superpowers_version = $version
  skills = $CoreSkills
  python = $pythonPath
} | ConvertTo-Json -Depth 4))

# Pin the gate to an absolute interpreter: a hook that cannot start fails open.
$hooksPath = Join-Path $pluginTarget 'hooks\hooks.json'
$escaped = ($pythonPath -replace '\\', '\\')
$template = Get-Content -LiteralPath $hooksPath -Raw
$expected = ([regex]::Matches($template, '"command": "python"')).Count
$hooks = $template.Replace('"command": "python"', "`"command`": `"$escaped`"")
$parsed = $hooks | ConvertFrom-Json
$pinned = @($parsed.hooks.PSObject.Properties | ForEach-Object { $_.Value } | ForEach-Object { $_.hooks } | Where-Object { $_.command -eq $pythonPath }).Count
if ($expected -eq 0 -or $pinned -ne $expected) { throw "Pinned $pinned of $expected gate hooks; hooks.json no longer matches the template." }
[IO.File]::WriteAllText($hooksPath, $hooks)
Write-Host "  deployed $($CoreSkills.Count) Core skills and the completion gate."

Write-Host '[3/4] Validating the plugin...'
if (Get-Command claude -ErrorAction SilentlyContinue) {
  $validation = & claude plugin validate $pluginTarget 2>&1
  if ($LASTEXITCODE -ne 0) { throw "claude plugin validate failed:`n$($validation -join "`n")" }
  Write-Host '  claude plugin validate: OK'
} else {
  Write-Warning '  claude is not installed; plugin validation skipped.'
}

Write-Host '[4/4] Installing shims...'
if ($SkipShims) {
  Write-Host '  skipped (-SkipShims).'
} else {
  New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
  $launcher = Join-Path $TargetRoot 'claude-lane.ps1'
  foreach ($lane in @('core', 'ds')) {
    $content = "@echo off`r`npowershell -NoProfile -ExecutionPolicy Bypass -File `"$launcher`" $lane %*`r`n"
    Set-Content -Path (Join-Path $BinDir "claude-$lane.cmd") -Value $content -Encoding ASCII
  }
  Write-Host "  installed claude-core and claude-ds in $BinDir."
}
Write-Host 'CLAUDE_LANE_SETUP_OK'
