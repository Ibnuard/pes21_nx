"""Generate local career metadata from the exact accepted runtime snapshot.

Never changes a CPK, registry, roster, or asset. Membership/order/shirts/ratings
come from its paired roster include; identity/name/portrait come from verified
identity state, with FL26 provenance fallback from the paired scorer namespace.
Generated native metadata stays in ignored local-debug, never the public tree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import unicodedata
from pathlib import Path

from build_fl26_cup_catalog import decoded_member, index_cpk
from convert_efootball10_players import PES21_ABILITY_BITS, read_bits

ROOT = Path(__file__).resolve().parents[1]


def build(catalog: dict, roster_text: str, identities: dict,
          scorer_text: str, native_records: dict[int, bytes]) -> tuple[str, dict]:
    match = re.search(r'#define PES21_PLAYER_MIGRATION_BUILD_ID "([0-9a-f]{16})"', roster_text)
    if not match:
        raise ValueError("Missing paired roster build ID")
    pair = match[1]
    # Selector JSON retains its own content hash across native-presentation
    # stages. The actual loose pair is checked against manifest + team include
    # by main(), not that historical JSON field.
    arrays = {}
    for team, kind, body in re.findall(
        r'exhibition_migration_team_(\d+)_(players|shirts)\[\]\s*=\s*\{(.*?)\};',
        roster_text, re.S,
    ):
        arrays[(int(team), kind)] = [int(n) for n in re.findall(r'\b(\d+)u?\b', body)]
    ratings_body = roster_text.split('exhibition_player_migration_canary_ratings[] = {', 1)[1].split('};', 1)[0]
    ratings = {int(n): (int(o), int(p)) for n, o, p in
               re.findall(r'\{(\d+)u?,\s*(\d+)u?,\s*(\d+)u?\}', ratings_body)}
    persons = {}
    for p in identities['identities'].values():
        if p.get('status') != 'active' or not p.get('native_sha256'):
            continue
        native = int(p['native_player_id'])
        if native in persons:
            raise ValueError(f'Duplicate native identity {native}')
        persons[native] = p
    # This table covers all roster identities, not only the sixteen scorer candidates.
    scorer_ids_body = scorer_text.split('league_scorer_identities[] = {', 1)[1].split('};', 1)[0]
    scorer_ids = {int(n): int(b) for n,b in re.findall(r'\{(\d+)u,\s*(\d+)u\}', scorer_ids_body)}
    rows, owned, canonical, retained = [], set(), set(), []
    normalized_shirts = 0
    for team in sorted(catalog['teams'], key=lambda t: int(t['team_id'])):
        tid = int(team['team_id'])
        if team['kind'] != 'club' or 'WORLD' in str(team.get('category','')).upper():
            continue
        players = arrays.get((tid,'players'), [])
        shirts = arrays.get((tid,'shirts'), [])
        if not 11 <= len(players) <= 40 or len(shirts) != len(players):
            raise ValueError(f'Invalid career roster {tid}')
        # Keep native order exactly; the lineup-role audit owns formation changes.
        used_shirts = set()
        reserved_shirts = {n for n in shirts if 1 <= n <= 99}
        for native, shirt in zip(players,shirts):
            p = persons.get(native)
            if not p or native not in native_records:
                raise ValueError(f'Unverified career identity {tid}/{native}')
            record=native_records[native]
            if hashlib.sha256(record).hexdigest()!=p['native_sha256']:
                raise ValueError(f'Native identity fingerprint changed: {native}')
            registry = p.get('registry',{})
            identity = int(p.get('base_id') or scorer_ids.get(native) or 0)
            if not identity or native in owned or identity in canonical:
                raise ValueError(f'Duplicate/missing club ownership {tid}/{native}/{identity}')
            if not p.get('base_id') and not identity & 0x80000000:
                raise ValueError('Local-only player has no proven disjoint identity')
            name = ' '.join(unicodedata.normalize('NFKD',p.get('name') or registry.get('canonical_name',''))
                            .encode('ascii','ignore').decode().split())[:47]
            position=(struct.unpack_from('<I',record,52)[0]>>18)&15
            # Career simulation strength, NOT a claimed native OVR. Retain the
            # authored OVR where supplied; otherwise derive from native role
            # abilities. This does not modify the on-field attributes.
            fields=[bit for key,bit in PES21_ABILITY_BITS.items()
                    if key.startswith('gk_') == (position==0)]
            strength=round(sum(read_bits(record,bit+1,6)+40 for bit in fields)/len(fields))
            overall=ratings.get(native,(strength,position))[0]
            if not 1 <= shirt <= 99 or shirt in used_shirts:
                shirt = next(n for n in range(1,100) if n not in used_shirts | reserved_shirts)
                normalized_shirts += 1
            used_shirts.add(shirt)
            if not name or not 1 <= overall <= 99 or not 0 <= position <= 12 or not 0 <= shirt <= 99:
                raise ValueError(f'Invalid career player metadata {native}')
            portrait = int(registry.get('portrait_asset_id') or native)
            rows.append([identity,native,portrait,tid,overall,position,shirt,name])
            owned.add(native); canonical.add(identity)
        retained.append(tid)
    # A player's native record includes gameplay/identity fields not shown in
    # the menu. Pin these too, so an update cannot silently alter a career.
    fingerprints = [persons[row[1]]['native_sha256'] for row in rows]
    content = hashlib.sha256(json.dumps([rows,fingerprints],separators=(',',':')).encode()).hexdigest()
    lines = ['/* Generated local career metadata; do not commit extracted data. */',
             f'#define ML_CATALOG_CONTENT_ID "{content}"',
             f'#define ML_CATALOG_PAIR_ID "{pair}"',
             'static const MlCatalogPlayer ml_catalog_players[] = {']
    for row in rows:
        lines.append('  {' + ', '.join(f'{v}u' for v in row[:7]) + ', ' + json.dumps(row[7]) + '},')
    lines += ['};', '#define ML_CATALOG_PLAYER_COUNT ((uint32_t)(sizeof(ml_catalog_players)/sizeof(ml_catalog_players[0])))', '']
    return '\n'.join(lines), {'pair_id':pair,'content_id':content,'clubs':len(retained),
                               'players':len(rows),'teams':retained,
                               'career_only_normalized_shirts':normalized_shirts}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog',type=Path,required=True)
    parser.add_argument('--rosters',type=Path,required=True)
    parser.add_argument('--identities',type=Path,required=True)
    parser.add_argument('--scorers',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--player-cpk',type=Path,required=True)
    args=parser.parse_args()
    output=args.output.resolve()
    if (ROOT/'local-debug').resolve() not in output.parents:
        raise ValueError('Native metadata output must remain in local-debug')
    index,base=index_cpk(args.player_cpk)
    raw=decoded_member(args.player_cpk,index,base,'common/etc/pesdb/Player.bin')
    if len(raw)%312: raise ValueError('Invalid PES21 player table')
    native={struct.unpack_from('<I',raw,off+8)[0]:raw[off:off+312]
            for off in range(0,len(raw),312)}
    text,report=build(json.loads(args.catalog.read_text(encoding='utf-8')),
                      args.rosters.read_text(encoding='utf-8'),
                      json.loads(args.identities.read_text(encoding='utf-8')),
                      args.scorers.read_text(encoding='utf-8'),native)
    manifest=args.manifest.read_text(encoding='utf-8').splitlines()[0].split()
    if len(manifest)!=4 or manifest[0]!='PESNX_LOOSE_CPK_V2' or manifest[1]!=report['pair_id']:
        raise ValueError('Loose manifest/roster mismatch')
    team_include=args.catalog.parent/'exhibition_teams_migration_generated.inc'
    header='\n'.join(team_include.read_text(encoding='utf-8').splitlines()[:5])
    if report['pair_id'] not in header:
        raise ValueError('Selector include/roster mismatch')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(text,encoding='utf-8')
    output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({**{k:v for k,v in report.items() if k!='teams'},'output':str(output)}))


if __name__=='__main__':
    main()
