#!/usr/bin/env python3
"""Build a detached, opt-in trophy runtime canary with a paired rollback.

This does not install a runtime or prove hardware playback. The owned prop and
scene payloads stay in ignored local-debug. Entrance policy is explicit and
every unrelated current CPK manifest row must remain unchanged.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import tempfile
import zipfile

from elftools.elf.elffile import ELFFile

import audit_trophy_candidate as audit
from entrance_scene_canary import Cpk
from fixdemo_scene_table import parse_scene_table
from prepare_loose_cpk import (PATCH_OBB, checked_cpk, checked_dummy_obb,
                               digest, read_manifest, write_manifest)
import stage_trophy_ceremony as trophy

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "PESNX_TROPHY_TEST_PACKAGE_V1"
CPK = "LooseCpk/dt220_mobile_all.cpk"
MANIFEST = "LooseCpk/manifest.txt"
PAK = "PesMobile/Content/Paks/PesMobile-CinematicProps-Android_ETC1_P.pak"
MARKER = "trophy-canary.txt"
TARGETS = ("pes21_nx.nro", CPK, MANIFEST, PAK, MARKER)
CAPABILITY = b"PESNX trophy runtime canary v1"
ACCEPTED_NRO_SHA256 = "b6419c1e45f7e58ee49ba5aae66eea845096628875a74effb8c069e337ee35b5"
CURRENT_NATIVE_MANIFEST_SHA256 = "3de016b3a69eef46d2c11d93c9fe321b341bcf0f05d056c2b01ac8e377e2a0c3"
# These identities are the delivered updates, not values asserted by an
# arbitrary package proof. Logs later copied into update/ are not install targets.
V49_FILES = {
    "pes21_nx.nro": {"bytes": 83882911, "sha256": "3bba60b4af5f2e5d50bbf709095875b31b010833c9bdf098d2246d0bc129a634"},
    CPK: {"bytes": 32798720, "sha256": "3fe2308ad07e4d776fcd1bb816cecbd2b859072b908b467b2bc56ce1b7e28cbb"},
    MANIFEST: {"bytes": 2413, "sha256": "818577d8cac513e3833fd3a9ee10c64a64c8bd4845b4ea72f502b7ec87459e61"},
    PAK: {"bytes": 1379421, "sha256": "17673134cdf4c1c155fc11e271d9bdb69e525b1108d6ba14f618a9c7d67e1b5a"},
    MARKER: {"bytes": 256, "sha256": "a54399ceb844e14d4b6f9bb133ee8570be424c6dc51fcf69c46396d2a8c14ffa"},
}
V50_FILES = {
    "pes21_nx.nro": {"bytes": 83887007, "sha256": "9a41ba0049e84a1e5fea8ea74b464a1bbbb1c1f68424f71fba47c993406c6148"},
    CPK: {"bytes": 34215936, "sha256": "72db80088df2a1648b6c9be3576a35ee6a14e707cb8304c3c289592fe654fd27"},
    MANIFEST: {"bytes": 2413, "sha256": "2d895f0a525ca2ad3229d01348624d59c5ba606a9e3cde497607f87d3e73208e"},
    PAK: {"bytes": 1379421, "sha256": "17673134cdf4c1c155fc11e271d9bdb69e525b1108d6ba14f618a9c7d67e1b5a"},
    MARKER: {"bytes": 256, "sha256": "ca1125e833b637a6f5cd58634d414da3d0dac844eb1ceb0b17c51f9bec202227"},
}
# The delivered v51 kept all four cinematic payloads byte-identical to v50.
# Its NRO identity is separately pinned; a relabelled proof cannot authorize it.
V51_FILES = {name: dict(record) for name, record in V50_FILES.items()}
V51_FILES["pes21_nx.nro"] = {
    "bytes": 83895199,
    "sha256": "27ffaee2220453fbc0d2e0f094ee905c819592f10f7ce9b5e53c059e49bee8a0",
}


def measured(path: Path) -> dict:
    return {"bytes": path.stat().st_size, "sha256": digest(path)}


def marker_bytes(cpk_sha: str, manifest_sha: str, pak_sha: str) -> bytes:
    values = (cpk_sha, manifest_sha, pak_sha)
    if any(not re.fullmatch(r"[0-9a-f]{64}", value) or set(value) == {"0"}
           for value in values):
        raise ValueError("marker requires three nonzero lowercase SHA-256 hashes")
    return ("PESNX_TROPHY_CANARY_V1\n" + "".join(
        f"{key}_sha256={value}\n"
        for key, value in zip(("cpk", "manifest", "pak"), values))).encode("ascii")


def with_cinematic_row(manifest: dict, record: dict) -> dict:
    result = copy.deepcopy(manifest)
    next(row for row in result["files"] if row["name"] == Path(CPK).name).update(
        size=record["bytes"], sha256=record["sha256"])
    return result


def verified_upgrade(root: Path, manifest: dict) -> dict:
    """Authorize known delivered targets only, regardless of user-added logs."""
    proof = json.loads((root / "VERIFICATION.json").read_text(encoding="utf-8"))
    known = next(((name, entrance, files) for name, entrance, files in (
        ("delivered-v49", "native", V49_FILES), ("delivered-v50", "walkout", V50_FILES),
        ("delivered-v51", "walkout", V51_FILES))
        if proof.get("schema") == SCHEMA and proof.get("installed_files") == files), None)
    if known is None:
        raise ValueError("upgrade package is not a known delivered v49/v50/v51 identity")
    label, entrance, files = known
    if any(measured(root / "update" / name) != record for name, record in files.items()):
        raise ValueError(label + " upgrade target changed")
    expected = with_cinematic_row(manifest, files[CPK])
    if read_manifest(root / "update") != expected:
        raise ValueError(label + " upgrade has different non-cinematic baseline rows")
    if (root / "update" / MARKER).read_bytes() != marker_bytes(
            files[CPK]["sha256"], files[MANIFEST]["sha256"], files[PAK]["sha256"]):
        raise ValueError(label + " marker does not match its exact asset set")
    return {"name": label, "entrance": entrance, "nro": files["pes21_nx.nro"],
            "manifest": files[MANIFEST], "cpk_files": expected["files"],
            "marker": files[MARKER], "pak": files[PAK], "prop_required": True}


def inspect_build(build_root: Path, pair: str, asset_hashes: tuple[str, ...] = ()) -> dict:
    """Bind the packaged NRO to actual linked executable segments, not a label."""
    nro = build_root / "pes21_nx.nro"
    raw = nro.read_bytes()
    if len(raw) < 0x80 or raw[16:20] != b"NRO0" or CAPABILITY not in raw:
        raise ValueError("NRO is not an integrated trophy runtime canary")
    if pair.encode("ascii") not in raw:
        raise ValueError("NRO does not contain the selected runtime pair")
    if any(not re.fullmatch(r"[0-9a-f]{64}", value) or value.encode("ascii") not in raw
           for value in asset_hashes):
        raise ValueError("NRO does not pin the selected trophy CPK/PAK hashes")
    with (build_root / "pes21_nx.elf").open("rb") as stream:
        elf = ELFFile(stream)
        loads = [s for s in elf.iter_segments() if s["p_type"] == "PT_LOAD"]
        if len(loads) != 3:
            raise ValueError("unexpected ELF load segment count")
        for index, segment in enumerate(loads):
            start, size = struct.unpack_from("<II", raw, 0x20 + index * 8)
            if (start != segment["p_vaddr"] or segment["p_filesz"] > size or
                    start + size > len(raw)):
                raise ValueError("NRO/ELF segment layout mismatch")
            skip = 0x80 if index == 0 else 0
            expected = segment.data()[skip:]
            if raw[start + skip:start + skip + len(expected)] != expected:
                raise ValueError("NRO differs from linked ELF")
    return {**measured(nro), "elf_load_segments_match": True,
            "capability": CAPABILITY.decode(), "hardware_tested": False}


def verify_baseline(root: Path, manifest_path: Path,
                    cpk_roots: tuple[Path, ...] = ()) -> tuple[dict, dict]:
    """Verify a full current baseline without copying its OBB or CPK payloads.

    Explicit CPK roots are overlays, in highest-priority-first order. A present
    but corrupt overlay is rejected; it cannot silently fall back to old bytes.
    """
    if manifest_path.name != "manifest.txt" or manifest_path.parent.name != "LooseCpk":
        raise ValueError("baseline manifest must be LooseCpk/manifest.txt")
    manifest = read_manifest(manifest_path.parent.parent)
    if manifest["version"] != 2:
        raise ValueError("full LooseCpk V2 baseline required")
    dummy = root / PATCH_OBB
    if measured(dummy) != {"bytes": manifest["parent_obb_bytes"],
                           "sha256": manifest["parent_obb_sha256"]}:
        raise ValueError("baseline dummy OBB differs from selected manifest")
    checked_dummy_obb(dummy)
    sources = {}
    for row in manifest["files"]:
        path = next((folder / row["name"] for folder in (*cpk_roots, root / "LooseCpk")
                     if (folder / row["name"]).exists()), None)
        if path is None or path.is_symlink() or measured(path) != {
                "bytes": row["size"], "sha256": row["sha256"]}:
            raise ValueError("baseline CPK differs from selected manifest: " + row["name"])
        checked_cpk(path)
        sources[row["name"]] = path
    native = sources[Path(CPK).name]
    if digest(native) != trophy.BASELINE_DT220_SHA256:
        raise ValueError("unknown entrance/cinematic baseline; explicit merge is required")
    table = parse_scene_table(Cpk(native).read(trophy.ENTRANCE_TABLE), 1)
    if [scene["name"] for scene in table["scenes"]] != ["ENT_MOBILE_CMN"]:
        raise ValueError("accepted native entrance is absent")
    return manifest, sources


INSTALLER = r'''param(
  [Parameter(Mandatory=$true)][string]$RuntimeRoot,
  [string]$PackageRoot=$PSScriptRoot,
  [string]$BackupRoot='D:/PESNX-Cache/RuntimeRollback',
  [string]$RollbackDirectory,
  [switch]$CheckOnly,
  [switch]$VerifyInstalled
)
$ErrorActionPreference='Stop'
$names=@('pes21_nx.nro','LooseCpk/dt220_mobile_all.cpk','LooseCpk/manifest.txt',
  'PesMobile/Content/Paks/PesMobile-CinematicProps-Android_ETC1_P.pak','trophy-canary.txt')
function Hash-File([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Check-File([string]$Path,$Record) {
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf) -or
      (Get-Item -LiteralPath $Path).Length -ne $Record.bytes -or
      (Hash-File $Path) -ne $Record.sha256) { throw "Missing/changed file: $Path" }
}
function Measure-OptionalFile([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) { return $null }
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Expected file: $Path" }
  return @{bytes=(Get-Item -LiteralPath $Path).Length;sha256=(Hash-File $Path)}
}
function Same-Record($Actual,$Expected) {
  return ($null -ne $Actual -and $null -ne $Expected -and
    $Actual.bytes -eq $Expected.bytes -and $Actual.sha256 -eq $Expected.sha256)
}
function Record-Issue([string]$Name,$Actual,$Expected) {
  if ($null -eq $Actual) { return "MISSING $Name expected_sha256=$($Expected.sha256)" }
  if (-not (Same-Record $Actual $Expected)) {
    return "MISMATCH $Name expected_bytes=$($Expected.bytes) actual_bytes=$($Actual.bytes) expected_sha256=$($Expected.sha256) actual_sha256=$($Actual.sha256)"
  }
}
function Child-Path([string]$Root,[string]$Name) {
  $path=[IO.Path]::GetFullPath((Join-Path $Root $Name))
  $prefix=$Root.TrimEnd([IO.Path]::DirectorySeparatorChar,[IO.Path]::AltDirectorySeparatorChar)+[IO.Path]::DirectorySeparatorChar
  if (-not $path.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)) { throw 'Target escapes root' }
  $check=$path
  while ($check.Length -ge $Root.Length) {
    if (Test-Path -LiteralPath $check) {
      if ((Get-Item -LiteralPath $check -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Reparse-point target is unsupported: $check"
      }
    }
    if ($check -eq $Root) { break }
    $check=Split-Path -Parent $check
  }
  return $path
}
function Restore-Originals($State,[string]$SavedRoot) {
  # The exact target set was validated before calling this function.
  foreach ($name in $names) {
    $target=Child-Path $runtime $name
    $row=$State.originals.$name
    if ($row.existed) {
      Copy-Item -LiteralPath (Child-Path $SavedRoot $name) -Destination $target -Force
      Check-File $target $row
    } elseif (Test-Path -LiteralPath $target) {
      Remove-Item -LiteralPath $target -Force
    }
  }
}
function Check-BackupAncestors([string]$Path) {
  $check=[IO.Path]::GetFullPath($Path)
  while ($check) {
    if (Test-Path -LiteralPath $check) {
      if ((Get-Item -LiteralPath $check -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Backup path uses a reparse point: $check"
      }
    }
    $parent=Split-Path -Parent $check
    if ($parent -eq $check) { break }
    $check=$parent
  }
}
function Candidate-Issues {
  foreach ($name in $names) {
    if ($readErrors.ContainsKey($name)) { Write-Output $readErrors[$name] }
    else { Record-Issue $name $actualFiles[$name] $proof.installed_files.$name }
  }
  $expected=@{bytes=$proof.baseline.obb.bytes;sha256=$proof.baseline.obb.sha256}
  try { Record-Issue $proof.baseline.obb_name (Measure-OptionalFile (Child-Path $runtime $proof.baseline.obb_name)) $expected }
  catch { Write-Output "UNREADABLE $($proof.baseline.obb_name): $($_.Exception.Message)" }
  foreach ($row in $candidateRows) {
    $name='LooseCpk/'+$row.name
    if ($name -eq $names[1]) { continue } # Already measured among the five targets.
    try { Record-Issue $name (Measure-OptionalFile (Child-Path $runtime $name)) @{bytes=$row.size;sha256=$row.sha256} }
    catch { Write-Output "UNREADABLE ${name}: $($_.Exception.Message)" }
  }
  $pakDirectory=Split-Path -Parent (Child-Path $runtime $names[3])
  if (Test-Path -LiteralPath $pakDirectory -PathType Container) {
    Get-ChildItem -LiteralPath $pakDirectory -File | Where-Object {
      $_.Name -like '*CinematicProps*.pak' -and $_.Name -ne [IO.Path]::GetFileName($names[3])
    } | ForEach-Object { Write-Output "CONFLICT PesMobile/Content/Paks/$($_.Name)" }
  }
}
if ($VerifyInstalled -and ($CheckOnly -or $RollbackDirectory)) { throw 'VerifyInstalled is a separate read-only mode; do not combine it with CheckOnly or rollback' }
if (-not (Test-Path -LiteralPath $RuntimeRoot -PathType Container)) { throw 'RuntimeRoot must be an existing runtime directory' }
$resolvedRuntime=(Resolve-Path -LiteralPath $RuntimeRoot).Path
$runtime=$resolvedRuntime.TrimEnd([IO.Path]::DirectorySeparatorChar,[IO.Path]::AltDirectorySeparatorChar)
$rootPath=([IO.Path]::GetPathRoot($resolvedRuntime)).TrimEnd([IO.Path]::DirectorySeparatorChar,[IO.Path]::AltDirectorySeparatorChar)
if (-not $runtime -or $runtime -eq $rootPath) { throw 'RuntimeRoot must not be a drive/share root' }
foreach ($name in $names) { $null=Child-Path $runtime $name }
if ($RollbackDirectory) {
  $saved=(Resolve-Path -LiteralPath $RollbackDirectory).Path
  $state=Get-Content -LiteralPath (Join-Path $saved 'ROLLBACK.json') -Raw | ConvertFrom-Json
  if ($state.schema -ne 'PESNX_TROPHY_ROLLBACK_V1' -or $state.runtime -ne $runtime -or
      (@($state.originals.PSObject.Properties.Name | Sort-Object) -join '|') -ne
      (@($names | Sort-Object) -join '|') -or
      (@($state.installed.PSObject.Properties.Name | Sort-Object) -join '|') -ne
      (@($names | Sort-Object) -join '|')) { throw 'Rollback belongs to another runtime or target set' }
  foreach ($name in $names) {
    $current=Child-Path $runtime $name
    $old=$state.originals.$name
    if ($old.existed) { Check-File (Child-Path $saved $name) $old }
    # An interrupted installation can contain a mixture of original/new files.
    # Any third hash is a later/unrecognized update and must be preserved.
    if (Test-Path -LiteralPath $current -PathType Leaf) {
      $hash=Hash-File $current
      if ($hash -ne $state.installed.$name.sha256 -and
          (-not $old.existed -or $hash -ne $old.sha256)) { throw "Rollback target changed: $name" }
    } elseif ($old.existed) { throw "Original/installed file absent: $name" }
  }
  if ($CheckOnly) { Write-Output 'Rollback preflight OK; no writes'; exit 0 }
  Restore-Originals $state $saved
  Write-Output 'Original NRO, cinematic pair and prop/marker state restored. Saves unchanged.'
  exit 0
}
$package=(Resolve-Path -LiteralPath $PackageRoot).Path.TrimEnd([IO.Path]::DirectorySeparatorChar,[IO.Path]::AltDirectorySeparatorChar)
$proof=Get-Content -LiteralPath (Join-Path $package 'VERIFICATION.json') -Raw | ConvertFrom-Json
if ($proof.schema -ne 'PESNX_TROPHY_TEST_PACKAGE_V1' -or
    @($proof.baseline_states).Count -lt 1 -or
    (@($proof.installed_files.PSObject.Properties.Name | Sort-Object) -join '|') -ne
    (@($names | Sort-Object) -join '|')) { throw 'Unsupported package/target set' }
foreach ($name in $names) {
  Check-File (Child-Path $package ('update/'+$name)) $proof.installed_files.$name
}
# Derive the complete candidate manifest from the validated baseline contract.
# The only modified CPK row is dt220. Never treat five matching target hashes as
# proof that all other runtime files also match this installation.
$candidateRows=@($proof.baseline.cpk_files | ForEach-Object {
  if ($_.name -eq 'dt220_mobile_all.cpk') {
    [pscustomobject]@{name=$_.name;size=$proof.installed_files.($names[1]).bytes;sha256=$proof.installed_files.($names[1]).sha256}
  } else { $_ }
})
$candidateLines=@(Get-Content -LiteralPath (Child-Path $package ('update/'+$names[2])))
if ($candidateLines.Count -ne $candidateRows.Count+1 -or
    $candidateLines[0] -ne $proof.baseline.manifest_header) { throw 'Candidate manifest header/count differs from runtime identity' }
for ($i=0; $i -lt $candidateRows.Count; $i++) {
  $row=$candidateRows[$i]
  if ($row.name -notmatch '^[a-z0-9_]+\.cpk$' -or
      $candidateLines[$i+1] -ne "$($row.name) $($row.size) $($row.sha256)") { throw 'Candidate manifest rows differ from runtime identity' }
}
$manifestPath=Child-Path $runtime 'LooseCpk/manifest.txt'
$marker=Child-Path $runtime 'trophy-canary.txt'
$pak=Child-Path $runtime $names[3]
# Hash these identities once. Only a whole recognized state is installable;
# a mixture from an interrupted/manual overlay is not silently promoted.
$actualFiles=@{}
$readErrors=@{}
$targetsMatch=$true
foreach ($name in $names) {
  try { $actualFiles[$name]=Measure-OptionalFile (Child-Path $runtime $name) }
  catch { $readErrors[$name]="UNREADABLE ${name}: $($_.Exception.Message)" }
  if ($readErrors.ContainsKey($name) -or -not (Same-Record $actualFiles[$name] $proof.installed_files.$name)) { $targetsMatch=$false }
}
if ($VerifyInstalled -or $targetsMatch) {
  $issues=@(Candidate-Issues)
  if ($issues.Count) {
    $issues | ForEach-Object { Write-Output $_ }
    Write-Output 'Installed candidate verification FAILED; no files were written or removed.'
    exit 1
  }
  Write-Output "Installed candidate verified: all five targets, $($candidateRows.Count) CPKs and dummy OBB match. NRO sha256=$($actualFiles['pes21_nx.nro'].sha256)"
  if (-not $VerifyInstalled) { Write-Output 'Already installed; no-op. No backup or file changes needed.' }
  else { Write-Output 'Read-only verification complete; saves and logs unchanged. This verifies installed files, not which NRO is currently running.' }
  exit 0
}
$actualNro=$actualFiles['pes21_nx.nro']
$actualManifest=$actualFiles[$names[2]]
$actualMarker=$actualFiles[$names[4]]
$actualPak=$actualFiles[$names[3]]
$selected=$null
foreach ($candidate in @($proof.baseline_states)) {
  if (-not (Same-Record $actualNro $candidate.nro) -or
      -not (Same-Record $actualManifest $candidate.manifest)) { continue }
  if ($null -eq $candidate.marker) {
    if ($null -ne $actualMarker) { continue }
  } elseif (-not (Same-Record $actualMarker $candidate.marker)) { continue }
  if ($null -eq $actualPak) {
    if ($candidate.prop_required) { continue }
  } elseif (-not (Same-Record $actualPak $candidate.pak)) { continue }
  $selected=$candidate
  break
}
if ($null -eq $selected) { throw 'Installed NRO, manifest, marker and prop PAK are not one supported complete baseline; preserve files and inspect their provenance' }
Check-File (Child-Path $runtime $proof.baseline.obb_name) $proof.baseline.obb
$lines=@(Get-Content -LiteralPath $manifestPath)
if ($lines.Count -ne $selected.cpk_files.Count+1 -or
    $lines[0] -ne $proof.baseline.manifest_header) { throw 'Installed manifest is not the accepted baseline' }
for ($i=0; $i -lt $selected.cpk_files.Count; $i++) {
  $row=$selected.cpk_files[$i]
  if ($row.name -notmatch '^[a-z0-9_]+\.cpk$' -or
      $lines[$i+1] -ne "$($row.name) $($row.size) $($row.sha256)") { throw 'Invalid CPK baseline contract' }
  Check-File (Child-Path $runtime ('LooseCpk/'+$row.name)) @{bytes=$row.size;sha256=$row.sha256}
}
$pakDir=Split-Path -Parent $pak
if (-not (Test-Path -LiteralPath $pakDir -PathType Container)) { throw 'Runtime Paks directory absent' }
$conflicts=@(Get-ChildItem -LiteralPath $pakDir -File | Where-Object {
  $_.Name -like '*CinematicProps*.pak' -and $_.Name -ne [IO.Path]::GetFileName($pak)
})
if ($conflicts.Count) { throw 'Another cinematic-prop PAK is present; preserve it and resolve its provenance first' }
$backupParent=[IO.Path]::GetFullPath($BackupRoot)
if ($backupParent -ne [IO.Path]::GetPathRoot($backupParent)) {
  $backupParent=$backupParent.TrimEnd([IO.Path]::DirectorySeparatorChar,[IO.Path]::AltDirectorySeparatorChar)
}
Check-BackupAncestors $backupParent
foreach ($reserved in @($runtime,$package)) {
  if ($backupParent -eq $reserved -or $backupParent.StartsWith($reserved+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) {
    throw 'Rollback must be stored outside the runtime and package'
  }
}
if ($CheckOnly) { Write-Output "Trophy canary preflight OK; complete baseline $($selected.name) verified; entrance policy $($proof.entrance_policy); no writes"; exit 0 }
$saved=Join-Path $backupParent ('trophy-'+[DateTime]::Now.ToString('yyyyMMdd-HHmmss')+'-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $saved | Out-Null
$state=@{schema='PESNX_TROPHY_ROLLBACK_V1';runtime=$runtime;originals=@{};installed=$proof.installed_files}
foreach ($name in $names) {
  $target=Child-Path $runtime $name
  $row=@{existed=(Test-Path -LiteralPath $target -PathType Leaf)}
  if ($row.existed) {
    $row.bytes=(Get-Item -LiteralPath $target).Length
    $row.sha256=Hash-File $target
    $copy=Child-Path $saved $name
    New-Item -ItemType Directory -Path (Split-Path -Parent $copy) -Force | Out-Null
    Copy-Item -LiteralPath $target -Destination $copy
    Check-File $copy $row
  }
  $state.originals[$name]=$row
}
$state | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $saved 'ROLLBACK.json') -Encoding UTF8
try {
  # Marker is installed last, after NRO, CPK/manifest and PAK all match.
  foreach ($name in $names) {
    $target=Child-Path $runtime $name
    Copy-Item -LiteralPath (Child-Path $package ('update/'+$name)) -Destination $target -Force
    Check-File $target $proof.installed_files.$name
  }
} catch {
  Restore-Originals $state $saved
  throw
}
Write-Output "Installed opt-in trophy canary. Rollback: $saved"
Write-Output "Restore: .\Apply-Update.ps1 -RuntimeRoot '$runtime' -RollbackDirectory '$saved'"
Write-Output "Entrance policy: $($proof.entrance_policy). Other CPKs, faces, OBB and saves unchanged. Hardware playback still needs testing."
'''


INSTRUCTIONS = """FootballNX - folder siap copy (kandidat uji)

1. Tutup game sebelum mengganti file.
2. Buka folder update, lalu salin SEMUA isinya ke folder game yang berisi
   pes21_nx.nro. Gabungkan folder dan timpa file dengan nama yang sama.
3. Pastikan trophy-canary.txt ikut berada di samping pes21_nx.nro.
   Salin LooseCpk/dt220_mobile_all.cpk dan LooseCpk/manifest.txt sebagai pasangan.
   PAK cup/podium ikut berada di PesMobile/Content/Paks.

Folder update sudah lengkap: NRO, pasangan CPK/manifest, PAK dan marker.
Tidak ada save atau OBB yang disertakan. Jangan salin folder update sebagai
subfolder baru di dalam folder game; salin ISINYA.
@ENTRANCE_DESCRIPTION@

Uji singkat: final Custom Cup dua tim (MU vs Barca), satu leg, sampai menang.
Saat full time, tunggu tanpa menekan Skip: periksa piala lalu match overview.
Periksa juga intro pemain berjalan masuk tetap ada. Simpan trophy-runtime.log
dan scene-runtime.log terbaru untuk diagnosis.
Validasi file belum membuktikan trophy tampil atau performa di Switch.

OPSIONAL - pemeriksaan dari PC, tanpa mengubah file:
  powershell -ExecutionPolicy Bypass -File .\\Apply-Update.ps1 -RuntimeRoot 'E:/switch/pes21_nx' -VerifyInstalled

Ganti E:/switch/pes21_nx dengan folder game sebenarnya. Pemeriksaan mencantumkan
file yang hilang atau berbeda, termasuk NRO dan marker, serta memeriksa semua CPK
dan dummy OBB. Save dan log tidak diubah. Ini memeriksa file terpasang, bukan NRO
yang sedang berjalan. Log lama saja bukan bukti versi NRO yang dijalankan.

OPSIONAL - pemasangan dengan backup otomatis, sebagai alternatif copy manual:
  powershell -ExecutionPolicy Bypass -File .\\Apply-Update.ps1 -RuntimeRoot 'E:/switch/pes21_nx' -CheckOnly
  powershell -ExecutionPolicy Bypass -File .\\Apply-Update.ps1 -RuntimeRoot 'E:/switch/pes21_nx'

Installer menerima baseline terverifikasi dalam VERIFICATION.json. Jika kandidat
yang sama sudah lengkap terpasang, hasilnya no-op tanpa backup/tulisan baru.
Backup tersimpan di D:/PESNX-Cache/RuntimeRollback; gunakan lokasi yang dicetak:
  powershell -ExecutionPolicy Bypass -File .\\Apply-Update.ps1 -RuntimeRoot 'E:/switch/pes21_nx' -RollbackDirectory '<lokasi-backup>'

Rollback hanya mengembalikan lima target ke kondisi sebelum installer dijalankan,
termasuk file yang sebelumnya tidak ada. Save, OBB, dan log tidak dipulihkan atau
dihapus. Paket/log tambahan di luar lima target tidak disalin oleh installer.
"""


SD_INSTRUCTIONS = """FootballNX - siap copy ke SD (kandidat uji)

1. Tutup game, lalu salin folder switch dari paket ini ke ROOT kartu SD.
   Gabungkan folder dan timpa file dengan nama yang sama.
2. Jalankan: sdmc:/switch/pes21_nx/pes21_nx.nro

Paket berisi lima file pembaruan yang sudah dicocokkan hash-nya dengan paket
utama. NRO, pasangan CPK/manifest, PAK trophy dan trophy-canary.txt harus ikut
tersalin bersama. Game dan aset dasar harus sudah ada di switch/pes21_nx.
Tidak ada save, OBB, log lama, atau skrip yang perlu dijalankan.

Tes utama: buat final Custom Cup dua tim (MU vs Barca), satu leg, lalu mainkan
sampai menang. Saat full time, tunggu tanpa menekan Skip: periksa apakah scene
angkat piala tampil, kemudian game lanjut ke match overview. Periksa juga intro
pemain berjalan masuk tetap ada. Pada tes terpisah, coba Skip saat piala tampil
dan pastikan overview tetap bisa dibuka.

Hasil pengujian di perangkat masih menunggu. Simpan scene-runtime.log dan trophy-runtime.log
terbaru untuk diagnosis; jangan mengganti log baru dengan log dari paket lama.
"""


def sd_copy_destination(package_root: Path, output: Path) -> tuple[Path, Path]:
    output, package_root = output.resolve(), package_root.resolve()
    archive = output.with_name(output.name + ".zip")
    if ((ROOT / "local-debug").resolve() not in output.parents or output.exists() or archive.exists()):
        raise ValueError("SD copy output and ZIP must be fresh inside ignored local-debug")
    if ({output, archive} & {package_root, package_root.with_suffix(".zip")} or
            package_root in output.parents or output in package_root.parents):
        raise ValueError("SD copy output must be separate from the canonical package")
    return output, archive


def stage_sd_copy(package_root: Path, output: Path) -> dict:
    """Stage the exact five proven payloads in an SD-root tree, without installs."""
    output, archive = sd_copy_destination(package_root, output)
    proof = json.loads((package_root / "VERIFICATION.json").read_text(encoding="utf-8"))
    if proof.get("schema") != SCHEMA or set(proof.get("installed_files", {})) != set(TARGETS):
        raise ValueError("canonical package has an unsupported target set")
    records = proof["installed_files"]
    if any(measured(package_root / "update" / name) != records[name] for name in TARGETS):
        raise ValueError("canonical payload changed; SD copy was not created")
    manifest = read_manifest(package_root / "update")
    cinematic = next(row for row in manifest["files"] if row["name"] == Path(CPK).name)
    if (manifest["build_id"] != proof.get("runtime_pair") or
            {"bytes": cinematic["size"], "sha256": cinematic["sha256"]} != records[CPK]):
        raise ValueError("canonical CPK and manifest are not the verified runtime pair")
    marker = marker_bytes(*(records[name]["sha256"] for name in (CPK, MANIFEST, PAK)))
    if (package_root / "update" / MARKER).read_bytes() != marker:
        raise ValueError("canonical marker does not match the selected payload pair")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sd-copy-", dir=output.parent) as temp:
        temporary = Path(temp)
        staging = temporary / "payload"
        runtime = staging / "switch/pes21_nx"
        runtime.mkdir(parents=True)
        staged_files = {}
        for name in TARGETS:
            target = runtime / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(package_root / "update" / name, target)
            if measured(target) != records[name]:
                raise ValueError("payload changed while preparing SD copy: " + name)
            staged_files["switch/pes21_nx/" + name] = records[name]
        note = staging / "BACA-DULU.txt"
        note.write_text(SD_INSTRUCTIONS, encoding="utf-8", newline="\n")
        staged_files[note.name] = measured(note)
        temporary_zip = temporary / "sd-copy.zip"
        with zipfile.ZipFile(temporary_zip, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
            for name in sorted(staged_files):
                zipped.write(staging / name, name)
        with zipfile.ZipFile(temporary_zip) as zipped:
            if set(zipped.namelist()) != set(staged_files) or len(zipped.infolist()) != len(staged_files):
                raise ValueError("SD ZIP member set differs")
            if zipped.testzip() is not None:
                raise ValueError("SD ZIP CRC verification failed")
            for name, expected in staged_files.items():
                with zipped.open(name) as member:
                    hasher = hashlib.sha256()
                    count = 0
                    while block := member.read(1024 * 1024):
                        hasher.update(block)
                        count += len(block)
                if {"bytes": count, "sha256": hasher.hexdigest()} != expected:
                    raise ValueError("SD ZIP payload hash differs: " + name)
        if output.exists() or archive.exists():
            raise ValueError("SD output appeared during validation; existing output preserved")
        staging.rename(output)
        temporary_zip.rename(archive)
    return {"directory": str(output), "zip": str(archive), **measured(archive),
            "copied_targets": len(TARGETS), "zip_crc_verified": True,
            "zip_payload_hashes_verified": True, "hardware_tested": False}


def build_package(*, build_root: Path, baseline_nro: Path, baseline_root: Path,
                  baseline_manifest: Path, baseline_cpk_roots: tuple[Path, ...],
                  trophy_report: Path, package_report: Path, cooked_audit: Path,
                  repak: Path, unrealpak: Path, output: Path, entrance_policy: str,
                  upgrade_package: Path | None = None,
                  upgrade_packages: tuple[Path, ...] = (),
                  sd_copy_output: Path | None = None) -> dict:
    output = output.resolve()
    if (ROOT / "local-debug").resolve() not in output.parents or output.exists():
        raise ValueError("use a fresh directory inside ignored local-debug")
    archive = output.with_suffix(".zip")
    if archive.exists():
        raise ValueError("package archive already exists")
    if sd_copy_output:
        sd_copy_destination(output, sd_copy_output)
    if digest(baseline_nro) != ACCEPTED_NRO_SHA256:
        raise ValueError("baseline NRO is not the accepted v48 production build")
    if entrance_policy not in ("native", "walkout"):
        raise ValueError("declare entrance policy explicitly: native or walkout")
    upgrade_roots = ((upgrade_package,) if upgrade_package else ()) + tuple(upgrade_packages)
    if upgrade_roots and entrance_policy != "walkout":
        raise ValueError("delivered canary upgrade requires the combined walkout entrance policy")
    if entrance_policy == "walkout" and digest(baseline_manifest) != CURRENT_NATIVE_MANIFEST_SHA256:
        raise ValueError("combined walkout requires the known current native manifest; other versions need an explicit reviewed migration")
    manifest, sources = verify_baseline(baseline_root, baseline_manifest, baseline_cpk_roots)
    trophy_check = (trophy.check_combined(trophy_report) if entrance_policy == "walkout"
                    else audit.check_trophy(trophy_report))
    if not trophy_check.get("working_walkout_preserved" if entrance_policy == "walkout" else "native_entrance_preserved"):
        raise ValueError("scene audit does not prove the declared entrance policy")
    upgrade_states = [verified_upgrade(root, manifest) for root in upgrade_roots]
    if len({state["name"] for state in upgrade_states}) != len(upgrade_states):
        raise ValueError("duplicate delivered upgrade identity")
    candidate_cpk = trophy_report.parent / "update" / CPK
    prop_report = audit.read(package_report, "PESNX_CINEMATIC_PROP_PACKAGE_V1")
    build = inspect_build(build_root, manifest["build_id"],
                          (trophy_check["dt220_sha256"], digest(Path(prop_report["package"]))))
    if digest(sources[Path(CPK).name]) != trophy.BASELINE_DT220_SHA256:
        raise ValueError("trophy and selected entrance baselines differ")
    # Audit extraction and staging stay on the output drive, never system TEMP.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="trophy-package-", dir=output.parent) as temp:
        temporary = Path(temp)
        props = audit.check_package(package_report, cooked_audit, repak, unrealpak, temporary)
        staging = temporary / "package"
        update = staging / "update"
        (update / "LooseCpk").mkdir(parents=True)
        (update / Path(PAK).parent).mkdir(parents=True)
        for source, name in ((build_root / "pes21_nx.nro", "pes21_nx.nro"),
                             (candidate_cpk, CPK), (Path(prop_report["package"]), PAK)):
            shutil.copy2(source, update / name)
        merged = with_cinematic_row(manifest, measured(candidate_cpk))
        write_manifest(update, merged)
        if read_manifest(update) != merged:
            raise ValueError("generated CPK/manifest pair does not roundtrip")
        (update / MARKER).write_bytes(marker_bytes(
            digest(update / CPK), digest(update / MANIFEST), digest(update / PAK)))
        (staging / "Apply-Update.ps1").write_text(INSTALLER, encoding="utf-8", newline="\n")
        entrance_description = (
            "Intro FL26 players-walking-in/lineup dipertahankan byte-identik.\n"
            "Aset walkout dan trophy sudah digabung dalam satu CPK."
            if entrance_policy == "walkout" else "Paket lama yang dipilih secara eksplisit ini mempertahankan intro native.")
        (staging / "INSTALL.txt").write_text(INSTRUCTIONS.replace("@ENTRANCE_DESCRIPTION@", entrance_description),
                                             encoding="utf-8", newline="\n")
        # Record the copied bytes and independently check every source identity.
        installed = {name: measured(update / name) for name in TARGETS}
        if (installed["pes21_nx.nro"] != {"bytes": build["bytes"], "sha256": build["sha256"]} or
                installed[CPK]["sha256"] != trophy_check["dt220_sha256"] or
                installed[PAK]["sha256"] != props["pak_sha256"]):
            raise ValueError("source changed during package creation")
        states = [{"name": "accepted-v48-native", "entrance": "native",
                   "nro": measured(baseline_nro), "manifest": measured(baseline_manifest),
                   "cpk_files": manifest["files"], "marker": None,
                   "pak": installed[PAK], "prop_required": False}]
        if entrance_policy == "walkout":
            combined_report = json.loads(trophy_report.read_text(encoding="utf-8"))
            walkout_cpk = Path(combined_report["walkout_report"]).parent / "update" / CPK
            walkout_record = measured(walkout_cpk)
            if walkout_record["sha256"] != trophy.WALKOUT_DT220_SHA256:
                raise ValueError("reviewed walkout source changed during packaging")
            walkout_manifest = with_cinematic_row(manifest, walkout_record)
            scratch = temporary / "supported-walkout-baseline"
            (scratch / "LooseCpk").mkdir(parents=True)
            write_manifest(scratch, walkout_manifest)
            states.append({**states[0], "name": "accepted-v48-walkout", "entrance": "walkout",
                           "manifest": measured(scratch / MANIFEST), "cpk_files": walkout_manifest["files"]})
        states.extend(upgrade_states)
        proof = {"schema": SCHEMA, "runtime_pair": manifest["build_id"], "build": build,
                 "status": "integrated_canary_pending_hardware",
                 "activation": "explicit_trophy_canary_marker",
                 "hardware_tested": False, "production_ready": False,
                 "active_runtime_modified": False, "entrance_policy": entrance_policy,
                 "native_entrance_preserved": entrance_policy == "native",
                 "working_walkout_preserved": entrance_policy == "walkout",
                 "save_data_included": False, "obb_copied": False,
                 "baseline": {"nro": measured(baseline_nro),
                              "manifest": measured(baseline_manifest),
                              "manifest_header": baseline_manifest.read_text(encoding="ascii").splitlines()[0],
                              "obb_name": PATCH_OBB,
                              "obb": {"bytes": manifest["parent_obb_bytes"],
                                      "sha256": manifest["parent_obb_sha256"]},
                              "cpk_files": manifest["files"]},
                 "baseline_states": states,
                 "asset_checks": {"trophy": trophy_check, "props": props},
                 "installed_files": installed}
        (staging / "VERIFICATION.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
        if output.exists():
            raise ValueError("output appeared during validation; existing directory preserved")
        # On this Windows workflow rename refuses an existing destination;
        # shutil.move would silently nest the package inside that destination.
        staging.rename(output)
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                zipped.write(path, path.relative_to(output).as_posix())
    result = {"directory": str(output), "zip": str(archive), **measured(archive), "verification": proof}
    if sd_copy_output:
        result["sd_copy"] = stage_sd_copy(output, sd_copy_output)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("build-root", "baseline-nro", "baseline-root", "baseline-manifest",
                 "trophy-report", "package-report", "cooked-audit", "repak", "unrealpak", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--baseline-cpk-root", action="append", type=Path, default=[],
                        help="current CPK overlay; first supplied root has highest priority")
    parser.add_argument("--entrance-policy", choices=("native", "walkout"), required=True,
                        help="explicit intro contract; walkout requires the combined cinematic report")
    parser.add_argument("--upgrade-package", dest="upgrade_packages", type=Path, action="append", default=[],
                        help="known delivered v49/v50/v51 package to accept as an upgrade baseline; repeatable")
    parser.add_argument("--sd-copy-output", type=Path,
                        help="optional separate fresh folder containing switch/pes21_nx and BACA-DULU.txt")
    args = vars(parser.parse_args())
    args["baseline_cpk_roots"] = tuple(args.pop("baseline_cpk_root"))
    args["upgrade_packages"] = tuple(args["upgrade_packages"])
    print(json.dumps(build_package(**args), indent=2))


if __name__ == "__main__":
    main()
