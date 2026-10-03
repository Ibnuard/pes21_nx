#!/usr/bin/env python3
"""Write a 19-team local kit-conversion scope from the staged selector."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selector", type=Path, default=ROOT /
                        "local-debug/fl26-bundesliga-indonesia-selector/exhibition_team_catalog_migration.json")
    parser.add_argument("--slot-plan", type=Path, default=ROOT /
                        "local-debug/fl26-bundesliga-native-slot-plan.json")
    parser.add_argument("--output", type=Path, default=ROOT /
                        "local-debug/fl26-bundesliga-indonesia-selector/kit-scope.json")
    args = parser.parse_args()
    if (ROOT / "local-debug").resolve() not in args.output.resolve().parents:
        raise ValueError("kit scope must stay in local-debug")
    if args.output.exists():
        raise FileExistsError(args.output)
    catalog = json.loads(args.selector.read_text(encoding="utf-8"))
    slots = json.loads(args.slot_plan.read_text(encoding="utf-8"))
    wanted = {int(row["logical_team_id"]) for row in slots["team_slots"]} | {5750}
    catalog["teams"] = [row for row in catalog["teams"]
                        if int(row["team_id"]) in wanted]
    if len(catalog["teams"]) != 19:
        raise ValueError("expected 18 Bundesliga clubs and Indonesia")
    catalog["counts"]["selector_teams"] = 19
    catalog.pop("content_id", None)
    args.output.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(json.dumps({"output": str(args.output), "teams": 19}))


if __name__ == "__main__":
    main()
