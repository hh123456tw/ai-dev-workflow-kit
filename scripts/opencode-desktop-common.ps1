# Shared helpers for the OpenCode Desktop mode wrappers.
$script:DesktopLog = Join-Path $env:LOCALAPPDATA 'OpenCode\mode-launcher.log'

function Write-DesktopLog([string]$Message) {
  try {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $script:DesktopLog) | Out-Null
    Add-Content -LiteralPath $script:DesktopLog -Value ("{0} {1}" -f (Get-Date).ToString('o'), $Message)
  } catch { }
}

function Fail-DesktopLaunch([string]$Message) {
  Write-DesktopLog "ERROR: $Message"
  try {
    Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue
    [System.Windows.Forms.MessageBox]::Show(
      "$Message`n`nLog: $script:DesktopLog",
      'OpenCode mode launcher',
      [System.Windows.Forms.MessageBoxButtons]::OK,
      [System.Windows.Forms.MessageBoxIcon]::Error) | Out-Null
  } catch {
    Write-Error $Message
  }
  exit 1
}

function Get-OpenCodeDesktopPath {
  $candidates = @(
    (Join-Path $env:LOCALAPPDATA 'Programs\OpenCode\OpenCode.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\opencode\OpenCode.exe'),
    (Join-Path $env:PROGRAMFILES 'OpenCode\OpenCode.exe')
  )
  foreach ($candidate in $candidates) {
    if (Test-Path -LiteralPath $candidate) { return $candidate }
  }
  $found = Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'Programs') -Filter 'OpenCode.exe' -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($found) { return $found.FullName }
  return $null
}
