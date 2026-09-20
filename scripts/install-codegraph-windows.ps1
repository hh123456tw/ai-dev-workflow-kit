param([switch]$Force)
$ErrorActionPreference = 'Stop'

$Version = 'v0.20.1'
$ReleaseBase = "https://github.com/codegraph-ai/CodeGraph/releases/download/$Version"
$InstallDir = Join-Path $env:USERPROFILE ".codegraph\bin\$Version"
$Assets = @(
  [ordered]@{
    Name = 'codegraph-server-win32-x64.exe'
    Sha256 = 'aa1b6108217c119af6ac444b8652a0eadcfe2c343bff78ead2edd15b6b7b15b1'
  },
  [ordered]@{
    Name = 'onnxruntime.dll'
    Sha256 = '52f8ebe8f08f369a44fed6d1cb680c7c89169795e1c2949ee25b88b538ef0948'
  }
)

if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
  throw 'curl.exe is required for resumable CodeGraph downloads.'
}
if (-not (Test-Path -LiteralPath $env:USERPROFILE)) {
  throw "USERPROFILE parent does not exist: $env:USERPROFILE"
}
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

foreach ($asset in $Assets) {
  $target = Join-Path $InstallDir $asset.Name
  $sidecar = "$target.sha256"
  $validExisting = $false
  if (Test-Path -LiteralPath $target) {
    $existingHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant()
    $validExisting = $existingHash -eq $asset.Sha256
    if (-not $validExisting -and -not $Force) {
      throw "Existing $target has checksum $existingHash, expected $($asset.Sha256). Re-run with -Force to replace this managed file."
    }
  }

  & curl.exe -L --fail --retry 10 --retry-all-errors --retry-delay 2 `
    -o $sidecar "$ReleaseBase/$($asset.Name).sha256"
  if ($LASTEXITCODE -ne 0) { throw "Checksum download failed for $($asset.Name) with exit code $LASTEXITCODE" }
  $publishedHash = ((Get-Content -LiteralPath $sidecar -Raw) -split '\s+')[0].ToLowerInvariant()
  if ($publishedHash -ne $asset.Sha256) {
    throw "Published sidecar for $($asset.Name) is $publishedHash, expected pinned hash $($asset.Sha256)."
  }

  if (-not $validExisting) {
    $partial = "$target.part"
    if ($Force -and (Test-Path -LiteralPath $partial)) { Remove-Item -LiteralPath $partial -Force }
    $resumeArgs = if (Test-Path -LiteralPath $partial) { @('-C', '-') } else { @() }
    & curl.exe -L --fail --retry 10 --retry-all-errors --retry-delay 2 @resumeArgs `
      -o $partial "$ReleaseBase/$($asset.Name)"
    if ($LASTEXITCODE -ne 0) { throw "Download failed for $($asset.Name) with exit code $LASTEXITCODE" }
    $downloadedHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $partial).Hash.ToLowerInvariant()
    if ($downloadedHash -ne $asset.Sha256) {
      throw "Downloaded $($asset.Name) has checksum $downloadedHash, expected $($asset.Sha256)."
    }
    Move-Item -LiteralPath $partial -Destination $target -Force
  }
}

$engine = Join-Path $InstallDir 'codegraph-server-win32-x64.exe'
$reportedVersion = (& $engine --version | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $reportedVersion -ne 'codegraph-server 0.20.1') {
  throw "Unexpected CodeGraph version output: $reportedVersion"
}

[ordered]@{
  version = '0.20.1'
  release = $Version
  executable_sha256 = $Assets[0].Sha256
  onnxruntime_sha256 = $Assets[1].Sha256
  verified_at = (Get-Date).ToString('o')
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $InstallDir 'install-manifest.json') -Encoding UTF8

Write-Host "CODEGRAPH_INSTALL_PASS version=0.20.1 path=$InstallDir"
