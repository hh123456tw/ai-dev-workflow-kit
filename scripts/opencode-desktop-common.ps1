# Shared helper: locate the installed OpenCode Desktop executable.
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
  throw 'OpenCode Desktop executable not found. Install OpenCode Desktop first.'
}
