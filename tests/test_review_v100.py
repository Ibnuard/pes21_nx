from pathlib import Path
import hashlib,json,shutil,subprocess,sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from pack_runtime_assets import pack_entries,verify
from test_gameplan_editor import function

def test_actual_environment_resolution_stays_fixed_through_repeated_handoffs(tmp_path):
    if not shutil.which('gcc'):pytest.skip('host C compiler unavailable')
    source=(ROOT/'source/ue4_hooks.c').read_text()
    assert 'exhibition_environment_generation' not in function(source,'exhibition_gameplan_begin_prematch')
    first=source.index('uint32_t pes_controller_stadium_time_preference(void)')
    functions=source[first:source.index('uint32_t pes_controller_stadium_weather(void)',first)]
    code=tmp_path/'environment.c';code.write_text('''#include <assert.h>
#include "match_preferences.h"
static uint32_t exhibition_time_preference=NX_TIME_RANDOM,exhibition_weather_preference=NX_WEATHER_RANDOM,
 exhibition_season_preference=NX_SEASON_RANDOM,exhibition_environment_resolved,exhibition_environment_generation=1,
 exhibition_settings_time_zone,exhibition_settings_weather,exhibition_settings_season;
static uint64_t ticks;static uint64_t armGetSystemTick(void){return ++ticks*71234567;}
'''+functions+'''
int main(void){exhibition_resolve_environment();uint32_t t=exhibition_settings_time_zone,
w=exhibition_settings_weather,s=exhibition_settings_season;assert(t<2 && w<3 && s<2);
for(unsigned i=0;i<100;i++)exhibition_resolve_environment();
assert(ticks==1 && t==exhibition_settings_time_zone && w==exhibition_settings_weather && s==exhibition_settings_season);
exhibition_time_preference=1;exhibition_weather_preference=2;exhibition_season_preference=1;
++exhibition_environment_generation;exhibition_resolve_environment();
assert(ticks==2 && exhibition_settings_time_zone==1 && exhibition_settings_weather==2 && exhibition_settings_season==1);
++exhibition_environment_generation;exhibition_resolve_environment();assert(ticks==3);
return 0;}''')
    exe=tmp_path/'environment.exe';subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror','-I',str(ROOT/'source'),str(code),'-o',str(exe)],check=True,capture_output=True)
    subprocess.run([str(exe)],check=True,capture_output=True,timeout=10)

def test_random_choices_repeat_modal_ownership_and_manager_scrolling(tmp_path):
    if not shutil.which('gcc'):pytest.skip('host C compiler unavailable')
    exe=tmp_path/'review.exe'
    result=subprocess.run(['gcc','-std=c11','-O1','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
        '-I',str(ROOT/'source'),'-I',str(ROOT/'tests'),str(ROOT/'tests/test_review_v100.c'),
        *[str(ROOT/'source'/n) for n in ('loading_popup.c','manager_league_motion.c','manager_league_plan.c','gameplan_preset.c')],
        '-lm','-pthread','-o',str(exe)],capture_output=True)
    assert result.returncode==0,result.stderr.decode(errors='replace')
    result=subprocess.run([str(exe)],cwd=tmp_path,capture_output=True,timeout=30)
    assert result.returncode==0,(result.stdout+result.stderr).decode(errors='replace')

def test_real_consolidated_archive_preserves_assets_and_has_no_enable_token():
    folder=ROOT/'local-debug/manager-review-v100/assets';report_path=folder/'CONSOLIDATION.json'
    if not report_path.exists():pytest.skip('ignored consolidated v100 fixture required')
    report=json.loads(report_path.read_text());actual=verify(folder/'FootballNX.assets')
    assert {k:actual[k] for k in ('bytes','sha256')}==report['archive']
    assert len(actual['entries'])==1838 and report['protected_members_exact']==1834
    assert 'referee-probe.txt' not in actual['entries']
    for name,pin in {**report['protected_entries'],**report['added_entries']}.items():assert actual['entries'][name]==pin
    assert report['referee_motion_unchanged'] and not report['active_runtime_installed']

def test_production_reader_loads_archive_first_and_validates_production_config(tmp_path):
    if not shutil.which('gcc'):pytest.skip('host C compiler unavailable')
    config=('PESNX_TROPHY_RUNTIME_V1\ncpk_sha256='+'3c2bc88b75211f08356f777d56b11e3430d3ea81815b4d165e35418da634c9a2'+
        '\nmanifest_sha256='+'1'*64+'\npak_sha256='+'18ac86c560e360b8a7f3caf4b4cff1200f0ad6a03ce0d4b92ed3976e12301d31'+'\n').encode()
    pack_entries({'Runtime/trophy.cfg':config,'ManagerLeague/unknown-club.png':b'canonical'},tmp_path/'FootballNX.assets')
    (tmp_path/'ManagerLeague').mkdir();(tmp_path/'ManagerLeague/unknown-club.png').write_bytes(b'stale loose copy')
    code=tmp_path/'reader.c';code.write_text('''#include <assert.h>
#include "runtime_assets.h"
#include "trophy_canary_config.h"
int main(void){size_t n=0;void *p=nx_asset_read_production("ManagerLeague/unknown-club.png",65536,&n);
assert(p && n==9 && !memcmp(p,"canonical",9));free(p);
p=nx_asset_read_archive(NX_ASSET_ARCHIVE,"Runtime/trophy.cfg",512,&n);TrophyCanaryConfig config;
assert(p && trophy_canary_parse(p,n,&config));((char*)p)[n-2]='x';assert(!trophy_canary_parse(p,n,&config));free(p);return 0;}''')
    exe=tmp_path/'reader.exe';subprocess.run(['gcc','-std=c11','-O1','-I',str(ROOT/'source'),str(code),'-o',str(exe)],check=True,capture_output=True)
    subprocess.run([str(exe)],cwd=tmp_path,check=True,capture_output=True,timeout=20)

def test_v100_recording_is_measured_three_db_above_v99():
    folder=ROOT/'local-debug/manager-review-v100/trophy-audio/stage-01'
    if not (folder/'AUDIO-REPORT.json').exists():pytest.skip('ignored reviewed source and staged bank required')
    report=json.loads((folder/'AUDIO-REPORT.json').read_text());bank=folder/report['runtime_asset']
    assert hashlib.sha256(bank.read_bytes()).hexdigest()==report['bank_sha256']
    assert report['gain_db']==0 and abs(report['measured_increase_db']-3)<.02
    assert report['clipped_samples']==0 and report['decoded_peak']<.96 and report['snr_db']>37
    assert report['independent_decoded_samples']==688128 and report['original_pcm_encoded_once']
    assert (ROOT/'source/trophy_audio_catalog.h').read_bytes()==(folder/'trophy_audio_catalog.h').read_bytes()
