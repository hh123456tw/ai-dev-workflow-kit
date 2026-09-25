param(
  [string]$RepoName = 'ai-dev-workflow-kit',
  [ValidateSet('private','public')][string]$Visibility = 'private'
)
$ErrorActionPreference='Stop'
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw 'GitHub CLI (gh) is required. Install it, run gh auth login, then retry.' }
Push-Location $RepoRoot
try {
  gh auth status | Out-Host
  $hasOrigin = git remote get-url origin 2>$null
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($hasOrigin)) {
    gh repo create $RepoName --$Visibility --source . --remote origin --push
  } else {
    git push -u origin HEAD
  }
} finally { Pop-Location }
