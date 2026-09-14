"""Generate the deterministic all-region national-team kit manifest.

The exhibition catalog is the authority for which national teams are exposed
by the Switch UI.  This generator deliberately keeps the existing physical
team IDs and roster data; the resulting manifest is consumed only by the
mobile kit conversion pipeline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "data/exhibition_team_catalog.json"
DEFAULT_OUTPUT = ROOT / "data/national_team_kit_overrides.json"

REGIONS = (
    ("national_europe", "NATIONAL EUROPE"),
    ("national_africa", "NATIONAL AFRICA"),
    ("national_north_america", "NATIONAL NORTH AMERICA"),
    ("national_south_america", "NATIONAL SOUTH AMERICA"),
    ("national_asia_oceania", "NATIONAL ASIA OCEANIA"),
)


def content_id(payload: dict) -> str:
    canonical = {key: value for key, value in payload.items() if key != "content_id"}
    encoded = json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def ascii_name(row: dict) -> str:
    source = str(row.get("source_name", ""))
    if source and "\ufffd" not in source:
        try:
            source.encode("ascii")
            return source
        except UnicodeEncodeError:
            pass
    return str(row["display_name"]).title()


def generate(catalog_path: Path) -> dict:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    national = [row for row in catalog["teams"] if row.get("kind") == "national"]
    leagues = []
    seen: set[int] = set()
    for region, label in REGIONS:
        rows = [row for row in national if row.get("category") == region]
        teams = []
        for order, row in enumerate(rows, 1):
            logical_id = int(row["team_id"])
            physical_id = int(row["physical_team_id"])
            if logical_id != physical_id:
                raise ValueError(
                    f"national team {logical_id} aliases physical slot {physical_id}"
                )
            if physical_id in seen:
                raise ValueError(f"duplicate national physical team ID {physical_id}")
            seen.add(physical_id)
            teams.append(
                {
                    "team_id": physical_id,
                    "order": order,
                    "official_name": ascii_name(row),
                    "catalog_integration": "existing",
                    "team_bin_policy": "preserve_existing",
                }
            )
        if not teams:
            raise ValueError(f"catalog has no teams for {region}")
        leagues.append(
            {
                "key": region,
                "label": label,
                "catalog_category": region,
                "teams": teams,
            }
        )
    if len(seen) != len(national):
        omitted = sorted(int(row["team_id"]) for row in national if int(row["team_id"]) not in seen)
        raise ValueError(f"unmapped national teams: {omitted}")
    payload = {
        "schema_version": 1,
        "scope": "all_national_teams_all_regions",
        "policy": {
            "runtime_integration": True,
            "preserve_existing_team_rows": True,
            "patch_real_kit_flag_only": True,
            "expected_team_count": len(national),
            "kit_variants": ["1st", "2nd", "GK1st"],
        },
        "sources": {
            "kit_cpks": [
                {"key": "dt34_base", "path": "Data/dt34_g4.cpk", "precedence": 0},
                {"key": "season_a", "path": "download/data_s2526a.cpk", "precedence": 1},
                {"key": "season_b", "path": "download/data_s2526b.cpk", "precedence": 2},
                {"key": "season_c", "path": "download/data_s2526c.cpk", "precedence": 3},
            ]
        },
        "leagues": leagues,
    }
    payload["content_id"] = content_id(payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = json.dumps(generate(args.catalog), indent=2, ensure_ascii=True) + "\n"
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != payload:
            raise SystemExit(f"stale national-team kit manifest: {args.output}")
        return
    args.output.write_text(payload, encoding="utf-8")
    print(f"Wrote {args.output} ({sum(len(x['teams']) for x in json.loads(payload)['leagues'])} teams)")


if __name__ == "__main__":
    main()
