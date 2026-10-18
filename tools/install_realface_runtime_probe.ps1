param(
  [Parameter(Mandatory=$true)][string]$RuntimeRoot,
  [string]$PackageRoot=$PSScriptRoot,
  [ValidateSet('production','diagnostic')][string]$Mode='production',
  [string]$BackupRoot='D:/PESNX-Cache/RuntimeRollback',
  [switch]$CheckOnly
)
$ErrorActionPreference='Stop'
$runtime=(Resolve-Path -LiteralPath $RuntimeRoot).Path
$package=(Resolve-Path -LiteralPath $PackageRoot).Path
$proof=Get-Content -LiteralPath (Join-Path $package 'VERIFICATION.json') -Raw | ConvertFrom-Json
if ($proof.candidate -ne 'Face runtime isolation v42') { throw 'Unsupported package' }
function Hash-File([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Read-Lines([string]$Path) { @(Get-Content -LiteralPath $Path) }
$newNro=Join-Path $package $(if ($Mode -eq 'production') {'update/pes21_nx.nro'} else {'diagnostic/pes21_nx.nro'})
$newCpk=Join-Path $package 'entrance-baseline/LooseCpk/dt220_mobile_all.cpk'
$referenceManifest=Join-Path $package 'entrance-baseline/LooseCpk/manifest.txt'
if ((Hash-File $newNro) -ne $proof.builds.$Mode.sha256 -or
    (Hash-File $newCpk) -ne $proof.baseline_cinematics.dt220_sha256 -or
    (Hash-File $referenceManifest) -ne $proof.baseline_cinematics.manifest_sha256) {
  throw 'Package file hash mismatch; runtime was not changed'
}
$manifestPath=Join-Path $runtime 'LooseCpk/manifest.txt'
$current=Read-Lines $manifestPath
$reference=Read-Lines $referenceManifest
$expectedHeader="PESNX_LOOSE_CPK_V2 $($proof.runtime_pair) $($proof.expected_patch_obb_bytes) "
if ($current.Count -ne $reference.Count -or $current[0] -ne $reference[0] -or
    -not $current[0].StartsWith($expectedHeader)) { throw 'Runtime manifest is not the paired V2 family' }
$updated=@($current)
$found=$false
for ($i=1;$i -lt $current.Count;$i++) {
  if ($current[$i] -notmatch '^([a-z0-9_]+\.cpk) ([1-9][0-9]*) ([0-9a-f]{64})$') { throw 'Invalid installed CPK manifest row' }
  $name=$Matches[1]; $size=[long]$Matches[2]
  if ($reference[$i].Split(' ')[0] -ne $name) { throw 'Runtime manifest names/order differ' }
  $file=Join-Path $runtime "LooseCpk/$name"
  if (-not (Test-Path -LiteralPath $file -PathType Leaf) -or (Get-Item -LiteralPath $file).Length -ne $size) {
    throw "Missing/wrong-sized installed CPK: $name"
  }
  if ($name -eq 'dt220_mobile_all.cpk') { $updated[$i]=$reference[$i]; $found=$true }
}
if (-not $found) { throw 'Cinematic CPK row absent' }
$oldNro=Join-Path $runtime 'pes21_nx.nro'
$oldCpk=Join-Path $runtime 'LooseCpk/dt220_mobile_all.cpk'
if (-not (Test-Path -LiteralPath $oldNro -PathType Leaf)) { throw 'Installed NRO absent' }
if ((Hash-File $oldCpk) -notin @($proof.baseline_cinematics.allowed_installed_dt220_sha256)) {
  throw 'Installed dt220 has unreviewed changes. Preserve it; use a validated entrance-only rollback instead of replacing unrelated cinematic work.'
}
# Preserve every unrelated CPK manifest row, including another agent's changes.
if ($CheckOnly) {
  Write-Output "Preflight OK: $Mode; paired NRO + native dt220; other CPK rows preserved; no writes"
  exit 0
}
$backup=Join-Path ([IO.Path]::GetFullPath($BackupRoot)) ('v42-'+[DateTime]::Now.ToString('yyyyMMdd-HHmmss')+'-'+[guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Path (Join-Path $backup 'LooseCpk') -Force | Out-Null
$targets=@($oldNro,$oldCpk,$manifestPath)
$saved=@((Join-Path $backup 'pes21_nx.nro'),(Join-Path $backup 'LooseCpk/dt220_mobile_all.cpk'),(Join-Path $backup 'LooseCpk/manifest.txt'))
for ($i=0;$i -lt $targets.Count;$i++) { Copy-Item -LiteralPath $targets[$i] -Destination $saved[$i] }
$marker=Join-Path $runtime 'cinematic-trace.txt'
try {
  Copy-Item -LiteralPath $newNro -Destination $oldNro -Force
  Copy-Item -LiteralPath $newCpk -Destination $oldCpk -Force
  [IO.File]::WriteAllText($manifestPath,($updated -join "`n")+"`n",[Text.Encoding]::ASCII)
  if ((Hash-File $oldNro) -ne $proof.builds.$Mode.sha256 -or
      (Hash-File $oldCpk) -ne $proof.baseline_cinematics.dt220_sha256) { throw 'Installed hash mismatch' }
  if (Test-Path -LiteralPath $marker -PathType Leaf) {
    Move-Item -LiteralPath $marker -Destination (Join-Path $backup 'cinematic-trace.txt')
  }
} catch {
  for ($i=0;$i -lt $targets.Count;$i++) { Copy-Item -LiteralPath $saved[$i] -Destination $targets[$i] -Force }
  throw
}
Write-Output "Installed $Mode; rollback of these three files: $backup"
Write-Output 'Face PAKs, other CPKs, OBB and saves were not changed.'
