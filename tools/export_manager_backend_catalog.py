"""Export an ignored, read-only backend seed from the exact accepted NRO pair.

No APK/OBB/CPK/native record bytes or assets are copied into the export. The
SQLite contains derived player metadata and stays local, outside the public tree.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import struct
import unicodedata

from build_fl26_cup_catalog import decoded_member, index_cpk
from convert_efootball10_players import pes21_abilities, pes21_name

ROOT = Path(__file__).resolve().parents[1]
ROLES = ('GK','CB','LB','RB','DMF','CMF','LMF','RMF','AMF','LWF','RWF','SS','CF')

def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def digest(path):
    with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def canonical(value): return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',value).casefold() if c.isalnum() and not unicodedata.combining(c))

def export(args):
    out=args.output.resolve()
    if out.exists(): raise ValueError('existing output preserved; choose a fresh SQLite path')
    if out.suffix not in ('.sqlite','.db','.sqlite3'): raise ValueError('SQLite output required')
    if ROOT==out.parent or (ROOT in out.parents and (ROOT/'local-debug') not in out.parents):
        raise ValueError('derived catalog must remain ignored/local or outside the repository')
    pins=read(args.build_inputs)
    for path in (args.rosters,args.scorers,args.manager_catalog):
        pin=next((v for k,v in pins.items() if Path(k).resolve()==path.resolve()),None)
        if not pin or digest(path)!=pin['sha256']: raise ValueError('accepted build input changed: '+path.name)
    team_include=args.catalog.parent/'exhibition_teams_migration_generated.inc'
    if not any(Path(k).resolve()==team_include.resolve() and digest(team_include)==v['sha256'] for k,v in pins.items()):
        raise ValueError('selector include is not pinned to the accepted build')
    catalog=read(args.catalog)
    selector_text=team_include.read_text(encoding='utf8')
    catalog_seal=hashlib.sha256(json.dumps({k:v for k,v in catalog.items() if k!='content_id'},
        sort_keys=True,separators=(',',':')).encode('utf8')).hexdigest()[:16]
    if catalog.get('content_id')!=catalog_seal or f'// Catalog content ID: {catalog_seal}' not in selector_text:
        raise ValueError('catalog JSON is not the exact paired selector catalog')
    roster=args.rosters.read_text(encoding='utf8')
    scorers=args.scorers.read_text(encoding='utf8')
    manager=args.manager_catalog.read_text(encoding='utf8')
    pair=re.search(r'PES21_PLAYER_MIGRATION_BUILD_ID "([0-9a-f]{16})"',roster)[1]
    if pair not in '\n'.join(team_include.read_text(encoding='utf8').splitlines()[:5]): raise ValueError('selector pair mismatch')
    binding=scorers.split('league_scorer_identities[] = {',1)[1].split('};',1)[0]
    identities={int(n):int(b) for n,b in re.findall(r'\{(\d+)u,\s*(\d+)u\}',binding)}
    rating_text=roster.split('exhibition_player_migration_canary_ratings[] = {',1)[1].split('};',1)[0]
    ratings={int(n):(int(o),int(p)) for n,o,p in re.findall(r'\{(\d+)u?,\s*(\d+)u?,\s*(\d+)u?\}',rating_text)}
    arrays={(int(t),k):[int(v) for v in re.findall(r'\b(\d+)u?\b',body)] for t,k,body in re.findall(
        r'exhibition_migration_team_(\d+)_(players|shirts)\[\]\s*=\s*\{(.*?)\};',roster,re.S)}
    ml={int(n):(int(b),int(portrait),int(team),int(ovr),int(role),json.loads('"'+name+'"'))
        for b,n,portrait,team,ovr,role,shirt,name in re.findall(
            r'\{(\d+)u,\s*(\d+)u,\s*(\d+)u,\s*(\d+)u,\s*(\d+)u,\s*(\d+)u,\s*(\d+)u,\s*"((?:[^"\\]|\\.)*)"\}',manager)}
    seal=read(args.baseline_summary)
    cpk_pin=seal['files']['switch/pes21_nx/LooseCpk/dt200_mobile_all.cpk']
    if digest(args.player_cpk)!=cpk_pin['sha256']: raise ValueError('player CPK is not the accepted v100 data')
    index,base=index_cpk(args.player_cpk)
    raw=decoded_member(args.player_cpk,index,base,'common/etc/pesdb/Player.bin')
    if len(raw)%312: raise ValueError('invalid native player record size')
    native={struct.unpack_from('<I',raw,i+8)[0]:raw[i:i+312] for i in range(0,len(raw),312)}
    wide=sqlite3.connect(args.reference_db.resolve().as_uri()+'?mode=ro',uri=True)
    wide.row_factory=sqlite3.Row
    reference={int(p['base_id']):dict(p) for p in wide.execute('SELECT * FROM players')}
    meta=dict(wide.execute('SELECT * FROM metadata'))
    wide.close()
    teams=[];members=[];players={};attributes=[];bindings=[];categories=[]
    for c in catalog['categories']:
        categories.append({'category_key':c['key'],'display_name':c.get('label',c.get('name',c['key'])),
            'sort_order':len(categories)})
    for t in catalog['teams']:
        tid=int(t['team_id']);ids=arrays.get((tid,'players'),[]);shirts=arrays.get((tid,'shirts'),[])
        if not 18<=len(ids)<=40 or len(ids)!=len(shirts) or len(set(ids))!=len(ids): raise ValueError(f'invalid runtime roster {tid}')
        eligible=t['kind']=='club' and 'WORLD' not in str(t['category']).upper()
        teams.append({'team_id':tid,'native_team_id':int(t['physical_team_id']),'display_name':t['display_name'],
            'kind':t['kind'],'category_key':t['category'],'badge_slot':int(t['badge_slot']),
            'pack_eligible':int(eligible),'sort_order':int(t['category_position'])})
        for order,(nid,shirt) in enumerate(zip(ids,shirts)):
            if nid not in native or nid not in identities: raise ValueError(f'missing explicit runtime identity {tid}/{nid}')
            rid=identities[nid];namespace='fl26' if rid&0x80000000 else 'ef'
            source_id=rid&0x7fffffff if namespace=='fl26' else rid
            key=f'{namespace}:{source_id}';record=native[nid];name=pes21_name(record)
            role=(struct.unpack_from('<I',record,52)[0]>>18)&15
            if not name or role>=len(ROLES): raise ValueError(f'invalid native name/position {nid}')
            ability=pes21_abilities(record)
            selected=[v for k,v in ability.items() if k.startswith('gk_')==(role==0)]
            strength=round(sum(selected)/len(selected))
            ovr=ratings[nid][0] if nid in ratings else strength
            if not 1<=ovr<=99 or any(not 40<=v<=103 for v in ability.values()): raise ValueError(f'invalid attribute range {nid}')
            if nid in ml and (ml[nid][0]!=rid or ml[nid][3]!=ovr or ml[nid][4]!=role):
                raise ValueError(f'Manager catalog does not agree with paired roster {nid}')
            ref=reference.get(rid) if namespace=='ef' else None
            reference_ok=bool(ref and ref['native_player_id']==nid and normalized(ref['canonical_name'])==normalized(name)
                              and ref['primary_position']==role)
            fingerprint=hashlib.sha256(record).hexdigest()
            if key in players:
                if players[key]['native_player_id']!=nid: raise ValueError('canonical identity duplicated in native slots: '+key)
            else:
                players[key]={'player_key':key,'source_namespace':namespace,'source_player_id':source_id,
                    'ef_base_id':source_id if namespace=='ef' else None,'runtime_identity':rid,
                    'native_player_id':nid,'display_name':name,'position':ROLES[role],'position_code':role,
                    'display_ovr':ovr,'ovr_source':'paired_roster_override' if nid in ratings else 'native_role_mean_v1',
                    'native_role_strength':strength,'native_record_sha256':fingerprint,
                    'identity_binding_sha256':hashlib.sha256(canonical([key,nid,name,fingerprint]).encode()).hexdigest(),
                    'reference_identity_fingerprint':ref['fingerprint'] if reference_ok else None,
                    'age_reference':ref['age'] if reference_ok else None,'height_cm':ref['height'] if reference_ok else None,
                    'weight_kg':ref['weight'] if reference_ok else None,'country_id_reference':ref['country_id'] if reference_ok else None,
                    'reference_profile_verified':int(reference_ok),'manager_catalog_member':int(nid in ml)}
                attributes.extend({'player_key':key,'attribute_key':k,'raw_value':v,
                    'normalized_bp':(int(v)-40)*10000//63,'source':'paired_native_player_v1'} for k,v in sorted(ability.items()))
                # References only. No face/commentary donor ownership is inferred.
                bindings.append({'player_key':key,'native_player_id':nid,'runtime_identity':rid,
                    'portrait_id':ml[nid][1] if nid in ml else None,
                    'face_owner_id':None,'commentary_owner_id':None,'asset_policy':'runtime_reference_only_no_donor_inference'})
            members.append({'team_id':tid,'player_key':key,'roster_order':order,'shirt_number':shirt,
                'is_club_membership':int(t['kind']=='club')})
    if len({p['native_player_id'] for p in players.values()})!=len(players): raise ValueError('native key collision')
    payload={'categories':categories,'teams':sorted(teams,key=lambda r:r['team_id']),
        'players':sorted(players.values(),key=lambda r:r['player_key']),
        'player_attributes':sorted(attributes,key=lambda r:(r['player_key'],r['attribute_key'])),
        'team_memberships':sorted(members,key=lambda r:(r['team_id'],r['roster_order'])),
        'runtime_bindings':sorted(bindings,key=lambda r:r['player_key'])}
    content=hashlib.sha256(canonical(payload).encode()).hexdigest()
    out.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(out)
    db.executescript('''
    PRAGMA foreign_keys=ON;
    CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE categories(category_key TEXT PRIMARY KEY,display_name TEXT NOT NULL,sort_order INTEGER NOT NULL);
    CREATE TABLE teams(team_id INTEGER PRIMARY KEY,native_team_id INTEGER UNIQUE NOT NULL,display_name TEXT NOT NULL,
      kind TEXT NOT NULL,category_key TEXT NOT NULL REFERENCES categories,badge_slot INTEGER NOT NULL,
      pack_eligible INTEGER NOT NULL CHECK(pack_eligible IN(0,1)),sort_order INTEGER NOT NULL);
    CREATE TABLE players(player_key TEXT PRIMARY KEY,source_namespace TEXT NOT NULL,source_player_id INTEGER NOT NULL,
      ef_base_id INTEGER UNIQUE,runtime_identity INTEGER UNIQUE NOT NULL,native_player_id INTEGER UNIQUE NOT NULL,
      display_name TEXT NOT NULL,position TEXT NOT NULL,position_code INTEGER NOT NULL,
      display_ovr INTEGER NOT NULL CHECK(display_ovr BETWEEN 1 AND 99),ovr_source TEXT NOT NULL,
      native_role_strength INTEGER NOT NULL,native_record_sha256 TEXT NOT NULL,identity_binding_sha256 TEXT NOT NULL,
      reference_identity_fingerprint TEXT,age_reference INTEGER,height_cm INTEGER,weight_kg INTEGER,
      country_id_reference INTEGER,reference_profile_verified INTEGER NOT NULL,manager_catalog_member INTEGER NOT NULL,
      UNIQUE(source_namespace,source_player_id));
    CREATE TABLE player_attributes(player_key TEXT NOT NULL REFERENCES players,attribute_key TEXT NOT NULL,
      raw_value INTEGER NOT NULL CHECK(raw_value BETWEEN 40 AND 103),normalized_bp INTEGER NOT NULL,
      source TEXT NOT NULL,PRIMARY KEY(player_key,attribute_key));
    CREATE TABLE team_memberships(team_id INTEGER NOT NULL REFERENCES teams,player_key TEXT NOT NULL REFERENCES players,
      roster_order INTEGER NOT NULL,shirt_number INTEGER NOT NULL,is_club_membership INTEGER NOT NULL,
      PRIMARY KEY(team_id,player_key),UNIQUE(team_id,roster_order));
    CREATE INDEX membership_player ON team_memberships(player_key,team_id);
    CREATE INDEX player_ovr_role ON players(display_ovr,position,player_key);
    CREATE TABLE runtime_bindings(player_key TEXT PRIMARY KEY REFERENCES players,native_player_id INTEGER UNIQUE NOT NULL,
      runtime_identity INTEGER UNIQUE NOT NULL,portrait_id INTEGER,face_owner_id INTEGER,commentary_owner_id INTEGER,
      asset_policy TEXT NOT NULL);
    CREATE VIEW v_team_rosters AS SELECT t.team_id,t.display_name AS team_name,t.kind,m.roster_order,m.shirt_number,
      p.* FROM team_memberships m JOIN teams t USING(team_id) JOIN players p USING(player_key);
    CREATE VIEW v_pack_candidates AS SELECT r.* FROM v_team_rosters r JOIN teams t USING(team_id)
      WHERE t.pack_eligible=1;
    ''')
    for table,rows in payload.items():
        if not rows: raise ValueError('empty export table '+table)
        cols=list(rows[0]);db.executemany(f'INSERT INTO {table} ({",".join(cols)}) VALUES ({",".join("?" for _ in cols)})',
            [tuple(row[k] for k in cols) for row in rows])
    metadata={'schema_version':'1','catalog_version':'1.0.0','catalog_content_sha256':content,
        'runtime_pair_id':pair,'manager_catalog_content_id':re.search(r'ML_CATALOG_CONTENT_ID "([0-9a-f]+)"',manager)[1],
        'client_checkpoint':'7e3564c6b8300fa4aefd55e75de537f3742d4643','player_cpk_sha256':cpk_pin['sha256'],
        'reference_master_content_id':meta.get('catalog_content_id','unknown'),
        'scope':'exact_v100_selector_all_teams','contains_player_ownership':'false',
        'identity_policy':'ef BaseId; explicitly disjoint fl26 source IDs; one player, many memberships',
        'data_policy':'derived local metadata only; no raw native bytes or game assets',
        'source_rosters_sha256':digest(args.rosters),'source_scorers_sha256':digest(args.scorers),
        'source_selector_sha256':digest(team_include),'source_manager_catalog_sha256':digest(args.manager_catalog)}
    db.executemany('INSERT INTO metadata VALUES (?,?)',sorted(metadata.items()))
    db.commit()
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
    assert db.execute('SELECT COUNT(*) FROM teams').fetchone()[0]==len(catalog['teams'])
    assert db.execute('SELECT COUNT(*) FROM players WHERE manager_catalog_member=1').fetchone()[0]==len(ml)
    assert db.execute('SELECT COUNT(*) FROM player_attributes').fetchone()[0]==len(players)*25
    counts={k:db.execute(f'SELECT COUNT(*) FROM {k}').fetchone()[0] for k in payload}
    db.close()
    report={'state':'accepted_runtime_catalog_export_verified','catalog_version':'1.0.0',
        'catalog_content_sha256':content,'sqlite_sha256':digest(out),'sqlite_bytes':out.stat().st_size,
        'runtime_pair_id':pair,'counts':counts,'team_kinds':dict(Counter(t['kind'] for t in teams)),
        'pack_eligible_teams':sum(t['pack_eligible'] for t in teams),'manager_players':len(ml),
        'player_identity_namespaces':dict(Counter(p['source_namespace'] for p in players.values())),
        'starter_60_69_players':sum(60<=p['display_ovr']<=69 for p in players.values()),
        'reference_profile_verified':sum(p['reference_profile_verified'] for p in players.values()),
        'integrity_check':'ok','foreign_key_violations':0,'source_payloads_modified':False,
        'ownership_included':False,'full_player_attributes':25,'source_metadata':metadata}
    out.with_suffix('.manifest.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='source_metadata'},indent=2),flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('catalog','rosters','scorers','manager-catalog','build-inputs','baseline-summary','player-cpk','reference-db','output'):
        p.add_argument('--'+name,type=Path,required=True)
    export(p.parse_args())

if __name__=='__main__':main()
