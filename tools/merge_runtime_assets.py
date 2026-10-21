"""Merge pinned local player/referee assets into a verified FootballNX.assets.

Only Animations/referee.nxra may replace a base member. The accepted seed,
probe token and every standalone roster member are added at fixed paths.
Game payloads and generated reports must remain in ignored local storage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pack_runtime_assets import PLAYER_AUDIO_PREFIX, pack_entries, read_archive

APPROVED_FILES = {
    "animations/referee.nxra": "Animations/referee.nxra",
    "commentary/players-v53.nxcp": "Commentary/players-v53.nxcp",
    "referee-probe.txt": "referee-probe.txt",
}
REPLACEMENT = "animations/referee.nxra"


def record(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def load_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require_report(actual: dict, expected: dict, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} differs from its pinned validation report")


def merge(base_archive: Path, base_report: Path, approved_root: Path,
          approved_report: Path, roster_archive: Path, roster_report: Path,
          output: Path) -> dict:
    """Verify all input pins, preserve protected bytes, then publish atomically."""
    inputs = [base_archive, base_report, approved_report, roster_archive, roster_report]
    inputs += [approved_root / name for name in APPROVED_FILES.values()]
    if output.resolve() in {path.resolve() for path in inputs}:
        raise ValueError("output would overwrite a merge input")
    baseline, members = read_archive(base_archive)
    require_report(baseline, load_report(base_report), "base archive")
    roster, audio = read_archive(roster_archive, namespace_prefix=PLAYER_AUDIO_PREFIX)
    require_report(roster, load_report(roster_report)["archive"], "roster archive")
    if "catalog-id.txt" not in audio or not any(name.startswith("audio/") for name in audio):
        raise ValueError("roster archive requires audio and catalog-id.txt")
    accepted = load_report(approved_report)["files"]
    additions = {}
    for key, relative in APPROVED_FILES.items():
        data = (approved_root / relative).read_bytes()
        require_report(record(data), accepted["switch/pes21_nx/" + relative], relative)
        additions[key] = data
    if additions["referee-probe.txt"].strip() != b"PESNX_REFEREE_PROBE_V1":
        raise ValueError("unrecognized referee probe token")
    if REPLACEMENT not in members:
        raise ValueError("base archive is missing the named referee replacement")
    for name, data in audio.items():
        additions[PLAYER_AUDIO_PREFIX + "/" + name] = data
    protected = {name: proof for name, proof in baseline["entries"].items() if name != REPLACEMENT}
    for name in additions:
        if name in members and name != REPLACEMENT:
            raise ValueError(f"unapproved replacement conflicts with base archive: {name}")
    merged = {**members, **additions}
    # pack_entries validates typed caps and the count before touching the output.
    result = pack_entries(merged, output)
    for name, proof in protected.items():
        require_report(result["entries"][name], proof, "protected member " + name)
    accepted_entries = {name: result["entries"][name] for name in sorted(additions)}
    accepted_hash = hashlib.sha256(json.dumps(accepted_entries, sort_keys=True,
                                             separators=(",", ":")).encode()).hexdigest()
    return {
        "state": "all_sources_and_readback_verified",
        "archive": {"bytes": result["bytes"], "sha256": result["sha256"],
                    "entries": len(result["entries"])},
        "base_archive": {"bytes": baseline["bytes"], "sha256": baseline["sha256"],
                         "entries": len(baseline["entries"])},
        "protected_entries": protected,
        "protected_members_exact": len(protected),
        "approved_replacement": {"path": REPLACEMENT, "before": baseline["entries"][REPLACEMENT],
                                 "after": result["entries"][REPLACEMENT]},
        "accepted_files": {name: result["entries"][name] for name in APPROVED_FILES},
        "roster_import": {"source": {"bytes": roster["bytes"], "sha256": roster["sha256"]},
                          "prefix": PLAYER_AUDIO_PREFIX, "members": len(audio),
                          "audio_recordings": len(audio) - 1,
                          "payload_bytes": sum(proof["bytes"] for proof in roster["entries"].values()),
                          "catalog_marker": result["entries"][PLAYER_AUDIO_PREFIX + "/catalog-id.txt"],
                          "all_members_exact": True},
        "accepted_entries_sha256": accepted_hash,
        "source_payloads_modified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-archive", type=Path, required=True)
    parser.add_argument("--base-report", type=Path, required=True)
    parser.add_argument("--approved-root", type=Path, required=True)
    parser.add_argument("--approved-report", type=Path, required=True)
    parser.add_argument("--roster-archive", type=Path, required=True)
    parser.add_argument("--roster-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report_inputs = [args.output, args.base_archive, args.base_report, args.approved_report,
                     args.roster_archive, args.roster_report]
    report_inputs += [args.approved_root / name for name in APPROVED_FILES.values()]
    if args.report.resolve() in {path.resolve() for path in report_inputs}:
        parser.error("report would overwrite a merge input/output")
    report = merge(args.base_archive, args.base_report, args.approved_root, args.approved_report,
                   args.roster_archive, args.roster_report, args.output)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {report['archive']['entries']} assets, {report['archive']['bytes']} bytes: {args.output}")


if __name__ == "__main__":
    main()
