"""Stage a pinned local production archive; never install or delete loose files."""
from pathlib import Path
import argparse,hashlib,json
from pack_runtime_assets import read_archive,pack_entries

def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def fingerprint(path):
    with path.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    return {'bytes':path.stat().st_size,'sha256':digest}

def consolidate(summary_path:Path,trophy:Path,trophy_report:Path,output:Path)->dict:
    summary=read(summary_path);base=Path(summary['directory']);prefix='switch/pes21_nx/'
    if output.exists():raise ValueError('use a new output; existing archive preserved')
    def owned(name):
        path=base/(prefix+name)
        if fingerprint(path)!=summary['files'][prefix+name]:raise ValueError('baseline differs: '+name)
        return path
    archive=owned('FootballNX.assets');before,members=read_archive(archive)
    if 'animations/referee.nxra' not in members:raise ValueError('reviewed referee motion is missing')
    expected=read(trophy_report)
    if expected['runtime_asset']!='Audio/trophy-user-hca-v100.acb' or fingerprint(trophy)!={
        'bytes':expected['bank_bytes'],'sha256':expected['bank_sha256']}:
        raise ValueError('trophy report/recording mismatch')
    marker=owned('trophy-canary.txt').read_bytes()
    old_header=b'PESNX_TROPHY_CANARY_V1\n'
    if not marker.startswith(old_header):raise ValueError('unsupported trophy pairing')
    config=b'PESNX_TROPHY_RUNTIME_V1\n'+marker[len(old_header):]
    additions={'audio/manager-league-pcm-v96.acb':owned('Audio/manager-league-pcm-v96.acb'),
        'audio/trophy-user-hca-v100.acb':trophy,
        'managerleague/unknown-club.png':owned('ManagerLeague/unknown-club.png'),
        'runtime/trophy.cfg':config}
    removed={name:before['entries'][name] for name in members if name=='referee-probe.txt'}
    protected={name:pin for name,pin in before['entries'].items() if name not in removed}
    for name in removed:members.pop(name)
    for name in additions:
        if name in members:raise ValueError('unexpected existing production member: '+name)
    after=pack_entries({**members,**additions},output)
    for name,pin in protected.items():
        if after['entries'][name]!=pin:raise ValueError('protected member changed: '+name)
    return {'state':'detached_production_archive_verified','archive':fingerprint(output),
        'entries':len(after['entries']),'protected_members_exact':len(protected),
        'protected_entries':protected,'added_entries':{name:after['entries'][name] for name in additions},
        'removed_obsolete_enable_tokens':removed,'baseline_summary':str(summary_path),
        'baseline_summary_sha256':fingerprint(summary_path)['sha256'],
        'referee_motion_unchanged':after['entries']['animations/referee.nxra']==before['entries']['animations/referee.nxra'],
        'source_payloads_modified':False,'loose_sources_removed':False,'active_runtime_installed':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-summary','trophy-bank','trophy-report','output','report'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    if a.report.resolve()==a.output.resolve():p.error('report cannot overwrite the archive')
    if a.report.exists():p.error('existing report preserved')
    result=consolidate(a.baseline_summary,a.trophy_bank,a.trophy_report,a.output)
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('protected_entries',)},indent=2))
