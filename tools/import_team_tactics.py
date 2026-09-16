"""Lock eFootballDB formation/lineup hints; player data remains PESDBTools-owned."""
import argparse
import concurrent.futures
import hashlib
import json
import time
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


def fetch_team(team_id, retries=3):
    url = f'https://api.efootballdb.com/api/2022/teams/{team_id}'
    last_error = None
    for attempt in range(retries):
        try:
            request = Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
            )
            with urlopen(request, timeout=30) as response:
                raw = response.read()
            team = convert_team(json.loads(raw))
            if team['team_id'] != team_id:
                raise ValueError('response team mismatch')
            team.update(url=url, sha256=hashlib.sha256(raw).hexdigest())
            return team
        except Exception as error:  # network failures are recorded in the lock
            last_error = error
            if attempt + 1 < retries:
                time.sleep(min(4, 2 ** attempt))
    raise RuntimeError(f'{url}: {last_error}')


def snapshot_team_ids(path):
    payload = json.loads(path.read_text(encoding='utf-8'))
    return [int(row['ef_team_id']) for row in payload['teams']]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--team', type=int, action='append', default=[])
    parser.add_argument(
        '--snapshot', type=Path,
        help='add every active ef_team_id from a locked migration snapshot',
    )
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=8)
    parser.add_argument('--retries', type=int, default=3)
    parser.add_argument(
        '--merge', type=Path,
        help='reuse already locked successful teams from this snapshot',
    )
    parser.add_argument(
        '--require-complete', action='store_true',
        help='fail after writing the report when any requested team failed',
    )
    args = parser.parse_args()
    requested = set(args.team)
    if args.snapshot:
        requested.update(snapshot_team_ids(args.snapshot))
    if not requested:
        parser.error('at least one --team or --snapshot is required')
    if not 1 <= args.jobs <= 32:
        parser.error('--jobs must be between 1 and 32')
    if not 1 <= args.retries <= 10:
        parser.error('--retries must be between 1 and 10')

    result = dict(
        schema_version=2,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        requested_team_ids=sorted(requested),
        teams={},
        errors={},
    )
    if args.merge and args.merge.is_file():
        previous = json.loads(args.merge.read_text(encoding='utf-8'))
        result['teams'].update({
            str(team_id): row
            for team_id, row in previous.get('teams', {}).items()
            if int(team_id) in requested
        })
    pending = sorted(requested - {int(value) for value in result['teams']})
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = {
            executor.submit(fetch_team, team_id, args.retries): team_id
            for team_id in pending
        }
        for future in concurrent.futures.as_completed(futures):
            team_id = futures[future]
            try:
                result['teams'][str(team_id)] = future.result()
            except Exception as error:
                result['errors'][str(team_id)] = str(error)
    result['teams'] = dict(sorted(result['teams'].items(), key=lambda row: int(row[0])))
    result['errors'] = dict(sorted(result['errors'].items(), key=lambda row: int(row[0])))
    result['counts'] = {
        'requested': len(requested),
        'locked': len(result['teams']),
        'errors': len(result['errors']),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(
        f'Locked {len(result["teams"])}/{len(requested)} teams '
        f'({len(result["errors"])} errors): {args.output}'
    )
    if args.require_complete and result['errors']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
