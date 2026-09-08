param(
  [string]$Distro = "Ubuntu",
  [int]$Jobs = 0,
  [string]$OutputDirectory = "",
  [switch]$DisablePesdbAuthoritativeOvr,
  [switch]$Diagnostics,
  [switch]$PerfTrace
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$oldProjectRoot = $env:PES21_NX_PROJECT_ROOT
$oldWslEnv = $env:WSLENV
$oldDiagnostics = $env:PES21_NX_DIAGNOSTICS
$oldPerfTrace = $env:PES21_NX_PERF_TRACE
$oldJobs = $env:PES21_NX_BUILD_JOBS
$oldOutputRoot = $env:PES21_NX_BUILD_OUTPUT_ROOT
$oldPesdbAuthoritativeOvr = $env:PES21_NX_PESDB_AUTHORITATIVE_OVR

try {
  $buildOutputRoot = if ($OutputDirectory) {
    [IO.Path]::GetFullPath((Join-Path $projectRoot $OutputDirectory))
  } else {
    $projectRoot
  }
  New-Item -ItemType Directory -Path $buildOutputRoot -Force | Out-Null
  $env:PES21_NX_PROJECT_ROOT = $projectRoot
  $env:PES21_NX_DIAGNOSTICS = if ($Diagnostics) { "1" } else { "0" }
  $env:PES21_NX_PERF_TRACE = if ($PerfTrace) { "1" } else { "0" }
  $env:PES21_NX_BUILD_JOBS = if ($Jobs -gt 0) { "$Jobs" } else { "" }
  $env:PES21_NX_BUILD_OUTPUT_ROOT = $buildOutputRoot
  $env:PES21_NX_PESDB_AUTHORITATIVE_OVR = if ($DisablePesdbAuthoritativeOvr) { "0" } else { "1" }
  $env:WSLENV = if ($oldWslEnv) {
    "$oldWslEnv`:PES21_NX_PROJECT_ROOT/p`:PES21_NX_DIAGNOSTICS`:PES21_NX_PERF_TRACE`:PES21_NX_BUILD_JOBS`:PES21_NX_BUILD_OUTPUT_ROOT/p`:PES21_NX_PESDB_AUTHORITATIVE_OVR"
  } else {
    "PES21_NX_PROJECT_ROOT/p`:PES21_NX_DIAGNOSTICS`:PES21_NX_PERF_TRACE`:PES21_NX_BUILD_JOBS`:PES21_NX_BUILD_OUTPUT_ROOT/p`:PES21_NX_PESDB_AUTHORITATIVE_OVR"
  }

  $buildScript = @'
set -euo pipefail

build_dir=$(mktemp -d /tmp/pes21_nx.XXXXXX)
trap 'rm -rf "$build_dir"' EXIT

tar -C "$PES21_NX_PROJECT_ROOT" \
  --exclude=.git --exclude=dist --exclude=build \
  --exclude=tools --exclude=tests --exclude=scripts --exclude='*.md' \
  --exclude='data/*.json' --exclude=data/exhibition_badges \
  --exclude=local-inputs --exclude=local-debug \
  --exclude=.codex-dex --exclude=.codex-jadx --exclude=.codex-pak \
  --exclude=clean-package-removed --exclude=logs --exclude='$out' \
  --exclude=prepared_assets --exclude=EFOOTBALL10_extracted \
  --exclude=offline-responses --exclude=runtime-unused-cpk \
  --exclude=assets --exclude=Download --exclude=PesMobile \
  --exclude=SaveData --exclude=UE4Game \
  --exclude='*.so' --exclude='*.obb' --exclude='*.pak' \
  --exclude='*.cpk' --exclude='*.cfg' --exclude='debug*.log' \
  --exclude='*.xapk' \
  --exclude=pes21_nx.nro --exclude=pes21_nx.elf --exclude=pes21_nx.nacp \
  -cf - . | tar -C "$build_dir" -xf -
cd "$build_dir"

export DEVKITPRO=/opt/devkitpro
export DEVKITA64=/opt/devkitpro/devkitA64
export PATH=/opt/devkitpro/devkitA64/bin:/opt/devkitpro/tools/bin:/usr/bin:/bin

make clean
jobs="${PES21_NX_BUILD_JOBS:-$(nproc)}"
make -j"$jobs" \
  DIAGNOSTICS="${PES21_NX_DIAGNOSTICS:-0}" \
  PERF_TRACE="${PES21_NX_PERF_TRACE:-0}" \
  PES_PESDB_AUTHORITATIVE_OVR="${PES21_NX_PESDB_AUTHORITATIVE_OVR:-1}"

cp pes21_nx.nro "$PES21_NX_BUILD_OUTPUT_ROOT/"
cp pes21_nx.elf "$PES21_NX_BUILD_OUTPUT_ROOT/"
cp pes21_nx.nacp "$PES21_NX_BUILD_OUTPUT_ROOT/"
'@

  $temporaryScript = Join-Path ([IO.Path]::GetTempPath()) "pes21_nx_build_$PID.sh"
  try {
    [IO.File]::WriteAllText(
      $temporaryScript,
      $buildScript,
      (New-Object Text.UTF8Encoding($false))
    )
    $drive = $temporaryScript.Substring(0, 1).ToLowerInvariant()
    $pathPart = $temporaryScript.Substring(2).Replace("\", "/")
    $linuxScript = "/mnt/$drive$pathPart"
    & wsl.exe -d $Distro -- bash $linuxScript
    if ($LASTEXITCODE -ne 0) {
      throw "WSL build failed with exit code $LASTEXITCODE."
    }
  } finally {
    Remove-Item -LiteralPath $temporaryScript -Force -ErrorAction SilentlyContinue
  }

  $builtNro = Join-Path $buildOutputRoot "pes21_nx.nro"
  $runtimeNro = Join-Path $projectRoot "dist\pes21_nx\pes21_nx.nro"
  if (-not $OutputDirectory -and
      (Test-Path -LiteralPath (Split-Path -Parent $runtimeNro))) {
    Copy-Item -LiteralPath $builtNro -Destination $runtimeNro -Force
  }

  Get-Item -LiteralPath $builtNro |
    Select-Object FullName, Length, LastWriteTime
  if (Test-Path -LiteralPath $runtimeNro) {
    Get-Item -LiteralPath $runtimeNro |
      Select-Object FullName, Length, LastWriteTime
  }
} finally {
  if ($null -eq $oldProjectRoot) {
    Remove-Item Env:PES21_NX_PROJECT_ROOT -ErrorAction SilentlyContinue
  } else {
    $env:PES21_NX_PROJECT_ROOT = $oldProjectRoot
  }
  if ($null -eq $oldWslEnv) {
    Remove-Item Env:WSLENV -ErrorAction SilentlyContinue
  } else {
    $env:WSLENV = $oldWslEnv
  }
  if ($null -eq $oldDiagnostics) {
    Remove-Item Env:PES21_NX_DIAGNOSTICS -ErrorAction SilentlyContinue
  } else {
    $env:PES21_NX_DIAGNOSTICS = $oldDiagnostics
  }
  if ($null -eq $oldPerfTrace) {
    Remove-Item Env:PES21_NX_PERF_TRACE -ErrorAction SilentlyContinue
  } else {
    $env:PES21_NX_PERF_TRACE = $oldPerfTrace
  }
  if ($null -eq $oldJobs) {
    Remove-Item Env:PES21_NX_BUILD_JOBS -ErrorAction SilentlyContinue
  } else {
    $env:PES21_NX_BUILD_JOBS = $oldJobs
  }
  if ($null -eq $oldOutputRoot) {
    Remove-Item Env:PES21_NX_BUILD_OUTPUT_ROOT -ErrorAction SilentlyContinue
  } else {
    $env:PES21_NX_BUILD_OUTPUT_ROOT = $oldOutputRoot
  }
  if ($null -eq $oldPesdbAuthoritativeOvr) {
    Remove-Item Env:PES21_NX_PESDB_AUTHORITATIVE_OVR -ErrorAction SilentlyContinue
  } else {
    $env:PES21_NX_PESDB_AUTHORITATIVE_OVR = $oldPesdbAuthoritativeOvr
  }
}
