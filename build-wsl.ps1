param(
  [string]$Distro = "Ubuntu",
  [switch]$Diagnostics,
  [switch]$PerfTrace
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$oldProjectRoot = $env:PES21_NX_PROJECT_ROOT
$oldWslEnv = $env:WSLENV
$oldDiagnostics = $env:PES21_NX_DIAGNOSTICS
$oldPerfTrace = $env:PES21_NX_PERF_TRACE

try {
  $env:PES21_NX_PROJECT_ROOT = $projectRoot
  $env:PES21_NX_DIAGNOSTICS = if ($Diagnostics) { "1" } else { "0" }
  $env:PES21_NX_PERF_TRACE = if ($PerfTrace) { "1" } else { "0" }
  $env:WSLENV = if ($oldWslEnv) {
    "$oldWslEnv`:PES21_NX_PROJECT_ROOT/p`:PES21_NX_DIAGNOSTICS`:PES21_NX_PERF_TRACE"
  } else {
    "PES21_NX_PROJECT_ROOT/p`:PES21_NX_DIAGNOSTICS`:PES21_NX_PERF_TRACE"
  }

  $buildScript = @'
set -euo pipefail

build_dir=$(mktemp -d /tmp/pes21_nx.XXXXXX)
trap 'rm -rf "$build_dir"' EXIT

tar -C "$PES21_NX_PROJECT_ROOT" \
  --exclude=.git --exclude=dist --exclude=build \
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
make -j"$(nproc)" \
  DIAGNOSTICS="${PES21_NX_DIAGNOSTICS:-0}" \
  PERF_TRACE="${PES21_NX_PERF_TRACE:-0}"

cp pes21_nx.nro "$PES21_NX_PROJECT_ROOT/"
cp pes21_nx.elf "$PES21_NX_PROJECT_ROOT/"
cp pes21_nx.nacp "$PES21_NX_PROJECT_ROOT/"
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

  $builtNro = Join-Path $projectRoot "pes21_nx.nro"
  $runtimeNro = Join-Path $projectRoot "dist\pes21_nx\pes21_nx.nro"
  if (Test-Path -LiteralPath (Split-Path -Parent $runtimeNro)) {
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
}
