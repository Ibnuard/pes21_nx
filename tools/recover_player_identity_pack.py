"""Recover kit-only release identity damage with globally reserved player slots.

Uses local, reviewed roster snapshots; never fetches or guesses new membership.
Run without --package first to inspect the allocation audit.
"""
import argparse
import collections
import hashlib
import io
import json
import re
import shutil
import struct
import unicodedata
from pathlib import Path

from PIL import Image
from apply_pesdb_efootball import apply_verified_fields
from build_barca_real_madrid_mobile_kit_canary import cpk_inventory, decode_wesys_payload, package_cpk, validate_cpk
from build_pesdb_famous_teams_candidate import member_payload, package_outer_obb, validate_outer_obb
from build_eng_spa_license_pack import encode_wesys
from build_madrid_preserve_order import restore_order
from pesdb import parse_player_records

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'local-debug/national-team-all-kits-v2'
GOOD = ROOT/'local-debug/eng-spa-all-kits-v3'
PLAYER = 'common/etc/pesdb/Player.bin'

def load(path):
    return json.loads(path.read_text(encoding='utf-8'))

def norm(name):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD',name).encode('ascii','ignore').decode().lower())

def raw_member(cpk, name):
    return decode_wesys_payload(member_payload(cpk,name),name)[0]

def rows(raw):
    assert len(raw)%312==0
    result={struct.unpack_from('<I',raw,i+8)[0]:raw[i:i+312] for i in range(0,len(raw),312)}
    assert len(result)==len(raw)//312
    return result

def parse_rosters(path):
    text=path.read_text(encoding='utf8')
    arrays={name:[int(x) for x in re.findall(r'(\d+)u?',body)] for name,body in
            re.findall(r'static const uint32_t (\w+)\[\] = \{(.*?)\};',text,re.S)}
    table={int(t):arrays[a] for t,a in re.findall(r'\{\s*(\d+)u?,\s*(\w+_players),',text) if a in arrays}
    for tid,array,offset,count in re.findall(r'\{(\d+)u, (\w+) \+ (\d+)u, \w+ \+ \d+u, (\d+)u\}',text):
        table[int(tid)]=arrays[array][int(offset):int(offset)+int(count)]
    return arrays,table

def build(out, package=False):
    out.mkdir(parents=True,exist_ok=True)
    current_cpk=BASE/'dt200-original-order.cpk'
    # dt241 is carried by the base national-kit OBB.  Prepare its index before
    # allocating replacement IDs so every fresh player keeps a real portrait
    # member (the CPK schema cannot safely add new members).
    obb=BASE/'patch.305030001.jp.nyan2021.pesam.obb'
    portrait_cpk=out/'base-dt241.cpk'
    if not portrait_cpk.exists():
        portrait_cpk.write_bytes(member_payload(obb,'Expansion/dt241_mobile_all.cpk'))
    portrait_inventory=cpk_inventory(portrait_cpk)
    portrait_ids=set()
    for member in portrait_inventory:
        match=re.fullmatch(r'common/player/(\d+)\.png',member)
        if match:
            portrait_ids.add(int(match.group(1)))
    current=rows(raw_member(current_cpk,PLAYER))
    good=rows(raw_member(GOOD/'dt200-original-order.cpk',PLAYER))
    names=parse_player_records(b''.join(current.values()),'pes21')
    meta=load(ROOT/'local-debug/pesdb-runtime-rosters-generated.json')
    snap=load(ROOT/'local-debug/pesdb-efootball-authentic-rosters-current-54-shirts.json')
    # Official Ajax/Al-Hilal announcement, 2026-07-17: the duplicate Saudi
    # variant is stale. Keep the Ajax membership for the same human identity.
    # https://english.ajax.nl/articles/marcos-leonardo-joins-ajax-from-al-hilal
    stale=16916896
    t=meta['teams']['17873']
    if stale in t['ordered_source_ids']:
        from generate_pesdb_runtime_rosters import choose_balanced_xi
        keep=[i for i,s in enumerate(t['ordered_source_ids']) if s!=stale]
        for key in ('ordered_source_ids','ordered_target_ids','ordered_shirts'):
            t[key]=[t[key][i] for i in keep]
        values=[(s,snap['players'][str(s)]['base_overall'],snap['players'][str(s)]['primary_position_index']) for s in t['ordered_source_ids']]
        xi,bench=choose_balanced_xi(values,t['formation_roles'])
        for key in ('ordered_source_ids','ordered_target_ids','ordered_shirts'):
            t[key]=[t[key][i] for i in xi+bench]
    ef=load(ROOT/'local-debug/efootball10-all-teams-patch/validation-report.json')['players']
    canonical={int(x['ef10_player_id']):int(x['pes21_player_id']) for x in ef}
    source_identity={int(x['pes21_player_id']):int(x['ef10_player_id']) for x in ef}
    protected=set(source_identity)
    tables={}
    for f in ('exhibition_rosters_pes21_generated.inc','exhibition_rosters_ef10.inc','exhibition_rosters_pesdb_generated.inc'):
        arrays,table=parse_rosters(ROOT/'source'/f)
        tables[f]=table
        protected.update(i for a in arrays.values() for i in a)
    # Also reserve legacy/runtime arrays and every assignment, even off-selector.
    arrays,_=parse_rosters(ROOT/'source/exhibition_rosters.inc')
    protected.update(i for a in arrays.values() for i in a)
    inv=cpk_inventory(current_cpk)
    for name,offset in (('PlayerAssignment.bin',4),('SpecialPlayerAssignment.bin',0)):
        full='common/etc/pesdb/'+name
        raw=raw_member(current_cpk,full)
        assert len(raw)%16==0
        protected.update(struct.unpack_from('<I',raw,i+offset)[0] for i in range(0,len(raw),16))
    deleted=set()
    dn='common/etc/pesdb/PlayerDeleteList.bin'
    if dn in inv:
        raw=raw_member(current_cpk,dn)
        deleted={struct.unpack_from('<I',raw,i)[0] for i in range(0,len(raw),4)}
        protected.update(deleted)
    wanted={int(s):int(t) for team in meta['teams'].values() for s,t in zip(team['ordered_source_ids'],team['ordered_target_ids'])}
    assert len(wanted)==sum(len(t['ordered_source_ids']) for t in meta['teams'].values())
    # Explicit reviewed EF10->PESDB identities plus matching base-ID/name pairs.
    reviewed={}
    for fn in ('pesdb-efootball-identity-map-all-active.json','pesdb-efootball-identity-map-famous-teams.json','pesdb-efootball-identity-map.json'):
        for efid,pid in load(ROOT/'local-debug'/fn)['map'].items():
            if int(efid) in canonical:
                target=canonical[int(efid)]
                if int(pid) in reviewed and reviewed[int(pid)]!=target:
                    raise ValueError(f'conflicting reviewed identity {pid}')
                reviewed[int(pid)]=target
    allocation={}
    used={}
    changes=[]
    candidates=[]
    conflicts=[]
    for sid,old in sorted(wanted.items()):
        player=snap['players'][str(sid)]
        baseid=sid%16777216
        target=reviewed.get(sid)
        if target is None:
            possible=canonical.get(baseid,baseid)
            if possible in names and norm(names[possible].name)==norm(player['player_name']):
                target=possible
        if target is not None:
            if target in used and used[target]!=sid:
                conflicts.append((target,used[target],sid,player['player_name']))
                continue
            allocation[sid]=target; used[target]=sid
        else:
            candidates.append((sid,old))
    if conflicts: raise ValueError(f'canonical club conflicts: {conflicts}')
    # Allocate from globally unreferenced Player.bin rows.  Portrait updates
    # below are limited to existing dt241 members because this CPK's TOC does
    # not support safely adding new common/player entries.
    free_pool=set(current)-protected-set(used)
    free=iter(sorted(free_pool))
    for sid,old in candidates:
        target=next(free,None)
        if target is None: raise ValueError('No globally unreferenced slots remain')
        allocation[sid]=target; used[target]=sid
    audit={'teams':len(meta['teams']),'players':len(wanted),'protected_ids':len(protected),
           'free_slots':len(free_pool),'canonical_players':len(wanted)-len(candidates),
           'fresh_reserved_slots':len(candidates),'remaps':[],'damaged_players':[]}
    result=dict(current)
    coverage=load(ROOT/'local-debug/pesdb-efootball-stable-3231-authoritative-patch/coverage-report.json')
    original_ratings={int(x['target_player_id']):x for x in coverage['applied_players']}
    for sid,old in sorted(wanted.items()):
        target=allocation[sid]; player=snap['players'][str(sid)]
        found=names[old].name if old in names else '<missing row>'
        if norm(found)!=norm(player['player_name']):
            audit['damaged_players'].append({'source':sid,'old':old,'expected':player['player_name'],'found':found})
        # Canonical identity keeps its original face/body/nationality fields.
        template=current[target] if sid not in dict(candidates) else good[old]
        patched,_=apply_verified_fields(template,player)
        patched=bytearray(patched); struct.pack_into('<I',patched,8,target)
        result[target]=bytes(patched)
        audit['remaps'].append({'source':sid,'old':old,'target':target,'name':player['player_name'],
                                'canonical':sid not in dict(candidates)})
    assert allocation[16781738]==4522
    final_names=parse_player_records(b''.join(result.values()),'pes21')
    assert all(norm(final_names[allocation[s]].name)==norm(snap['players'][str(s)]['player_name']) for s in wanted)
    # Noncanonical allocations must never replace an occupied identity.
    assert all(allocation[s] not in protected for s,_ in candidates)
    assert all(result[i]==current[i] for i in current if i not in used)
    (out/'Player.bin').write_bytes(encode_wesys(b''.join(result.values())))
    # Preserve exact squad ordering/shirts, remapping only IDs and sorted lookup tables.
    text=(ROOT/'source/exhibition_rosters_pesdb_generated.inc').read_text(encoding='utf8')
    remap={old:allocation[s] for s,old in wanted.items()}
    owners=sorted((allocation[s],int(tid)) for tid,t in meta['teams'].items() for s in t['ordered_source_ids'])
    text=re.sub(r'(static const ExhibitionPesdbPlayerOwner exhibition_pesdb_player_owners\[\] = \{).*?\n\};',
                lambda m:m[1]+'\n'+''.join(f'    {{{p}u, {t}u}},\n' for p,t in owners)+'};',text,flags=re.S)
    for tid,team in meta['teams'].items():
        pattern=rf'(static const uint32_t exhibition_pesdb_team_{tid}_players\[\] = \{{).*?\n\}};'
        ids=[allocation[s] for s in team['ordered_source_ids']]
        text,n=re.subn(pattern,lambda m:m[1]+'\n    '+', '.join(f'{i}u' for i in ids)+',\n};',text,flags=re.S)
        assert n==1
        pattern=rf'(static const uint8_t exhibition_pesdb_team_{tid}_shirts\[\] = \{{).*?\n\}};'
        text,n=re.subn(pattern,lambda m:m[1]+'\n    '+', '.join(str(i) for i in team['ordered_shirts'])+',\n};',text,flags=re.S)
        assert n==1
    # Rebuild ratings so relocated targets receive their own OVR, sorted uniquely.
    match=re.search(r'(static const \w+ (\w*player\w*(?:rating|overall)\w*)\[\] = \{)(.*?)\n\};',text,re.S|re.I)
    if not match: raise ValueError('rating table missing')
    good_names=parse_player_records(b''.join(good.values()),'pes21')
    ratings={int(a):(int(b),int(c)) for a,b,c in re.findall(r'\{(\d+)u, (\d+)u, (\d+)u\}',match[3])
             if int(a) in names and int(a) in good_names and norm(names[int(a)].name)==norm(good_names[int(a)].name)}
    for sid,old in wanted.items(): ratings[allocation[sid]]=tuple((original_ratings[old]['base_overall'],original_ratings[old]['position_after']))
    text=text[:match.start()]+match[1]+'\n'+''.join(f'    {{{p}u, {v[0]}u, {v[1]}u}},\n' for p,v in sorted(ratings.items()))+'};'+text[match.end():]
    (out/'exhibition_rosters_pesdb_generated.inc').write_text(text,encoding='utf8')
    # Audit each selectable team's effective source and ownership filtering.
    owner=dict(owners)
    catalog=load(ROOT/'data/exhibition_team_catalog.json')['teams']
    ef_table=tables['exhibition_rosters_ef10.inc']; native=tables['exhibition_rosters_pes21_generated.inc']
    oldtab=tables['exhibition_rosters_pesdb_generated.inc']
    audit['all_teams']=[]
    for team in catalog:
        tid=int(team['team_id'])
        ids=([allocation[s] for s in meta['teams'][str(tid)]['ordered_source_ids']] if str(tid) in meta['teams']
             else ef_table.get(tid,native.get(tid,[])))
        if tid==59:
            ids=parse_rosters(ROOT/'source/exhibition_rosters.inc')[0]['exhibition_latvia_players']
        ids=[i for i in ids if team['kind']=='national' or i not in owner or owner[i]==tid]
        audit['all_teams'].append({'team':tid,'name':team['display_name'],'count':len(ids),'ids':ids,
                                   'missing':[i for i in ids if i not in result]})
    club_owners=collections.defaultdict(list)
    by_team={int(t['team_id']):t for t in catalog}
    for team in audit['all_teams']:
        assert team['count']>=11 and not team['missing'],team
        assert len(team['ids'])==len(set(team['ids'])),team
        if by_team[team['team']]['kind']=='club':
            for pid in team['ids']: club_owners[pid].append(team['team'])
    audit['cross_club_duplicates']={p:t for p,t in club_owners.items() if len(t)>1}
    assert not audit['cross_club_duplicates']
    audit['ronaldo']={'id':4522,'clubs':club_owners[4522],
                       'portugal':4522 in next(t['ids'] for t in audit['all_teams'] if t['team']==6)}
    assert audit['ronaldo']=={'id':4522,'clubs':[18961],'portugal':True}
    (out/'audit.json').write_text(json.dumps(audit,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in audit.items() if k not in ('remaps','damaged_players','all_teams')},indent=2))
    print('damaged',len(audit['damaged_players']),'missing rosters',[(x['team'],x['name']) for x in audit['all_teams'] if x['count']<11])
    if not package: return
    # Repair native membership too, so native screens agree with the NRO.
    assignment_name='common/etc/pesdb/PlayerAssignment.bin'
    assignment=raw_member(current_cpk,assignment_name)
    physical={int(t['physical_team_id']) for t in meta['teams'].values()}
    records=[struct.unpack_from('<IIII',assignment,o) for o in range(0,len(assignment),16)]
    maxid=max(r[0] for r in records)
    club_physical={int(t['physical_team_id']) for t in catalog if t['kind']=='club'}
    records=[r for r in records if r[2] not in physical and not (r[2] in club_physical and r[1] in owner)]
    for tid,t in meta['teams'].items():
        for order,(sid,shirt) in enumerate(zip(t['ordered_source_ids'],t['ordered_shirts'])):
            maxid+=1
            records.append((maxid,allocation[sid],int(t['physical_team_id']),(order<<8)|shirt))
    assert len({r[0] for r in records})==len(records)
    assert all(r[1] in result for r in records)
    assignments=encode_wesys(b''.join(struct.pack('<IIII',*r) for r in records))
    # Keep Player.bin and InstallVersionPlayer.bin ID sets identical.  The
    # base tables contain a small legacy mismatch; retain rows for active
    # result IDs and add missing IDs with the normal v200 record version.
    install_name='common/etc/pesdb/InstallVersionPlayer.bin'
    install_raw=raw_member(current_cpk,install_name)
    install_rows=[struct.unpack_from('<II',install_raw,o) for o in range(0,len(install_raw),8)]
    result_ids=set(result)
    install_rows=[r for r in install_rows if r[0] in result_ids]
    present={r[0] for r in install_rows}
    install_rows.extend((pid,200) for pid in sorted(result_ids-present))
    install_rows.sort(key=lambda r:(r[1],r[0]))
    install_payload=encode_wesys(b''.join(struct.pack('<II',*r) for r in install_rows))
    assert {r[0] for r in install_rows}==result_ids
    updates={PLAYER:(out/'Player.bin').read_bytes(),install_name:install_payload,assignment_name:assignments}
    # Keep every active ID loadable. Preserve all other delete-list entries.
    active_ids={i for t in audit['all_teams'] for i in t['ids']}
    updates[dn]=encode_wesys(b''.join(struct.pack('<I',i) for i in sorted(deleted-active_ids)))
    portraits=portrait_cpk
    portrait_updates={}
    blank=io.BytesIO(); Image.new('RGBA',(128,128),(0,0,0,0)).save(blank,format='PNG')
    from import_efootball10_portraits import normalize_portrait
    from pesdb import decode_wesys
    ef_names=parse_player_records(decode_wesys(ROOT/'local-debug/efootball10-audit/tables/common/etc/pesdb/Player.bin'),'ef10')
    portrait_audit=[]
    for row in audit['remaps']:
        if row['canonical']: continue # existing correctly keyed EF10/original portrait
        sid=row['source']; pid=row['target']; baseid=sid%16777216
        raw_image=ROOT/f'local-debug/efootball10-all-teams-portraits/{baseid}.png'
        name=snap['players'][str(sid)]['player_name']
        data=blank.getvalue(); status='transparent_missing_verified_portrait'
        if baseid in ef_names and norm(ef_names[baseid].name)==norm(name) and raw_image.is_file():
            path=out/'portraits'/f'{pid}.png'; normalize_portrait(raw_image,path)
            data=path.read_bytes(); status='verified_ef10'
        portrait_name=f'common/player/{pid}.png'
        if portrait_name in portrait_inventory:
            portrait_updates[portrait_name]=data
            portrait_audit.append({'id':pid,'source':sid,'status':status})
        else:
            portrait_audit.append({'id':pid,'source':sid,'status':'no_dt241_member_fallback'})
    # Required regression: Ronaldo retains the exact original EF10 image bytes.
    ronaldopic=member_payload(portraits,'common/player/4522.png')
    audit['ronaldo']['portrait_sha256']=hashlib.sha256(ronaldopic).hexdigest()
    replacements={}
    for label,base,data in [('dt200',current_cpk,updates),('dt241',portraits,portrait_updates)]:
        inventory=cpk_inventory(base)
        actions={n:'replace' if n in inventory else 'add' for n in data}
        paths={}
        for i,(n,b) in enumerate(data.items()):
            path=out/'payloads'/label/f'{i}.bin'; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(b); paths[n]=str(path.resolve())
        merged=package_cpk(ROOT,out,label,base,actions,data,paths)
        final=out/f'{label}-original-order.cpk'
        if label == 'dt241':
            # repack_cpk_members preserves the original dt241 TOC order; its
            # parser cannot read this schema for a second restore pass.
            shutil.copyfile(merged['candidate'],final)
        else:
            restore_order(Path(merged['candidate']),final,list(inventory)+sorted(set(data)-set(inventory)))
        audit[label]=validate_cpk(base,final,actions,data)
        replacements[f'Expansion/{label}_mobile_all.cpk']=final
    target=out/obb.name
    mode,note=package_outer_obb(obb,target,replacements)
    audit['obb']=validate_outer_obb(obb,target,replacements,packaging_mode=mode)
    audit['portraits']=portrait_audit
    (out/'audit.json').write_text(json.dumps(audit,indent=2),encoding='utf8')
    print(json.dumps(audit['obb'],indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'local-debug/player-identity-recovery-v1')
    p.add_argument('--package',action='store_true')
    a=p.parse_args(); build(a.output,a.package)
