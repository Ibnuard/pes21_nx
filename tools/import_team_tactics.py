"""Lock eFootballDB formation/lineup hints; player data remains PESDBTools-owned."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


def convert_team(payload):
    team = payload['data']
    assignments = team['player_assignments']
    by_order = {int(a['order_number']): a for a in assignments}
    if len(by_order) != len(assignments):
        raise ValueError('duplicate assignment order')
    strategies = []
    for tactic in sorted(team['tactics'], key=lambda t: t['strategy_type']):
        slots = sorted((f for f in tactic['formations']
                        if int(f['formation_index']) == 0), key=lambda f: f['sort_index'])
        if [int(f['sort_index']) for f in slots] != list(range(11)):
            raise ValueError('formation must contain slots 0..10 exactly once')
        converted = []
        for slot in slots:
            i = int(slot['sort_index'])
            role, depth, width = (int(slot[k]) for k in ('position_role', 'x_coord', 'y_coord'))
            if not (0 <= role <= 12 and 0 <= depth <= 48 and 0 <= width <= 105):
                raise ValueError('invalid role or native coordinates')
            player = by_order[i]['player']
            converted.append(dict(role=role, depth=depth, width=width,
                                  preferred_base_id=int(player['base_pes_id']),
                                  preferred_name=player['player_name']))
        strategies.append(dict(strategy=int(tactic['strategy_type']), slots=converted))
    if not strategies:
        raise ValueError('missing tactics')
    return dict(team_id=int(team['pes_id']), name=team['english_name'], strategies=strategies)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--team', type=int, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = dict(schema_version=1, fetched_at=datetime.now(timezone.utc).isoformat(), teams={})
    for team_id in sorted(set(args.team)):
        url = f'https://api.efootballdb.com/api/2022/teams/{team_id}'
        request = Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
        with urlopen(request, timeout=30) as response:
            raw = response.read()
        team = convert_team(json.loads(raw))
        if team['team_id'] != team_id:
            raise ValueError('response team mismatch')
        team.update(url=url, sha256=hashlib.sha256(raw).hexdigest())
        result['teams'][str(team_id)] = team
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'Locked {len(result["teams"])} teams: {args.output}')


if __name__ == '__main__':
    main()
