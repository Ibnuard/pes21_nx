"""Optional original-native first-leg storage and aggregate calculation proof.

All executed code is read from the compatible ignored hash-pinned library.
Fake owned records and named dependency stubs isolate the native arithmetic;
no game code, target memory or proprietary binary is copied into public source.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import struct
import subprocess
import sys

import pytest
from test_fixdemo_trophy_result import Probe,ELF_SHA256

ROOT=Path(__file__).resolve().parents[1]
SET='_ZN5tmpdb5Match14Set1stLegScoreE8HomeAwayh'
GET='_ZNK5tmpdb5Match14Get1stLegScoreE8HomeAway'
ENV='_ZN9game_mode31SetTmpdbMatchToRegistryMatchEnvEPN5match8registry8MatchEnvERKN5tmpdb5MatchE'
MANAGER='_ZN7match2D6Screen7Manager19UpdateTimeScoreInfoEPKN5match8registry12Screen2dInfoEPKNS3_10RecordInfoEbb'
SECOND='_ZNK5match8registry8ModeInfo11IsSecondLegEv'
SCORE='_ZN7match2D6Screen4Time27UpdateSwfByDispStatus_ScoreEbRKNS1_10DispStatusE'
FUNCTIONS={
    SET:(0x6d47be0,0x14,'b4670bc366e657f1543cc2f5f59610b2a3f4abc6a0e51aceca00960aa2de2fcf'),
    GET:(0x6d47bc4,0x1c,'52a75a579867608ece0ee5054974c854dac88d9c10f5b83dcc2916e1d7f13777'),
    ENV:(0x7beacf0,0x150,'e718a3815e2c4a4060b6dc98cdf0ab54016fe91d19e082a5b31c73ec29d4bf03'),
    MANAGER:(0x7ca704c,0x438,'46d31963cca9b8dae9c21c5f8743169055341f338039eaf0b647734e7b77b53a'),
    SECOND:(0x680a410,0x14,'0b992552eeec2706e1b39b0c539e45a683206077e266d70db0675e6e47ff9f54'),
    SCORE:(0x7cbab40,0x310,'c354f6c66e1523c5fed748201a94938e354136f4dcb576bf362af1bf45b747c4'),
}


def native_contract():
    path=ROOT/'dist/pes21_nx/libUE4.so'
    if not path.is_file():pytest.skip('compatible ignored libUE4.so required')
    module=pytest.importorskip('elftools.elf.elffile')
    with path.open('rb') as stream:
        assert hashlib.file_digest(stream,'sha256').hexdigest()==ELF_SHA256
        stream.seek(0);elf=module.ELFFile(stream)
        table=elf.get_section_by_name('.dynsym');names=table.stringtable.data()
        rows=list(struct.iter_unpack('<IBBHQQ',table.data()))
        def name(index):
            offset=rows[index][0]
            return names[offset:names.find(b'\0',offset)].decode(errors='replace')
        symbols={name(i):(row[4],row[5]) for i,row in enumerate(rows) if row[3] and row[4]}
        def read(address,size):
            stream.seek(next(elf.address_offsets(address,size)));return stream.read(size)
        selected={name:symbols[name] for name in (SET,GET,ENV,MANAGER,SECOND,SCORE)}
        code={name:read(*symbol) for name,symbol in selected.items()}
        for symbol_name,(address,size,sha) in FUNCTIONS.items():
            assert selected[symbol_name]==(address,size)
            assert hashlib.sha256(code[symbol_name]).hexdigest()==sha
        plt=elf.get_section_by_name('.plt');rel=elf.get_section_by_name('.rela.plt')
        calls={plt['sh_addr']+32+i*16:name(row[1]>>32)
               for i,row in enumerate(struct.iter_unpack('<QQq',rel.data()))}
        constants={address:read(address,0x1000) for address in (0x85D9000,0x9497000)}
    return dict(symbols=selected,code=code,calls=calls,constants=constants)


def original_seed_chain(contract,seed,goals,leg):
    def no_call(_probe,name,_args):raise AssertionError(name)
    setter=Probe(contract,SET,no_call)
    match=Probe.BASE+0x1000
    setter.run(match,0,seed[0]);setter.run(match,1,seed[1])
    stored=bytes(setter.vm.mem_read(match,64))
    getter=Probe(contract,GET,no_call)
    getter.vm.mem_write(match,stored)
    assert (getter.run(match,0),getter.run(match,1))==seed
    def convert_callback(_probe,name,args):
        if name==GET:return getter.run(match,args[1])
        if name.endswith('GetMatchTimeEv'):return 10
        if name.endswith('GetMaxBenchEv'):return 17
        if name.endswith('GetMaxSubstitutionsEv'):return 5
        if 'SetIsSpecialGoldenGoal' in name or 'SetEmotional' in name:return None
        if 'tmpdb5Match' in name:return 0
        raise AssertionError(name)
    converter=Probe(contract,ENV,convert_callback)
    env=Probe.BASE+0x20000
    converter.vm.mem_write(match,stored)
    converter.run(env,match)
    environment=bytes(converter.vm.mem_read(env,128))
    assert tuple(environment[0x6a:0x6c])==seed
    mode=Probe.BASE+0x30000
    second=Probe(contract,SECOND,no_call)
    second.put(mode+0xc319,1 if leg==2 else 0 if leg==1 else 2,1)
    is_second=second.run(mode)
    assert is_second==(leg==2)
    manager=Probe.BASE+0x1000
    registry=Probe.BASE+0xa000
    flow=Probe.BASE+0x40000
    stats=Probe.BASE+0x10000
    dummy=Probe.BASE+0x70000
    def callback(probe,name,args):
        if name.endswith('GlobalRegistry12GetOrderInfoE8HomeAway'):return dummy
        if 'GetMemberInfoByOrderNo' in name or name.endswith('GetCardInfoEv'):return dummy
        if name.endswith('tmpdb7Manager11GetInstanceEv'):return dummy
        if name.endswith('Utility4Info8IsInGameEv'):return 1
        if name==SECOND:return is_second
        if 'GetMainTimer' in name or name.endswith('time13GetTimeupTimeEb'):
            probe.vm.reg_write(probe.reg('s0'),struct.unpack('<I',struct.pack('<f',60. if 'GetMain' in name else 2700.))[0])
            return None
        if name.endswith('RecordInfo13GetMatchStatsEv'):return stats
        if name.endswith('StatsTeamInfo8GetScoreE8HalfKind'):
            assert args[1]==5 # Native combined regular/extra-time goals, not PK score.
            assert args[0] in (stats,stats+0x4ba90)
            return goals[args[0]!=stats]
        if 'LocalSkin14GetCurrentType' in name or 'GetExecDemoKind' in name or 'GetIsBlackMatch' in name:return 0
        raise AssertionError(name)
    probe=Probe(contract,MANAGER,callback)
    probe.vm.mem_map(0x95c2000,0x1000)
    holder=Probe.BASE+0x9000
    probe.put(0x95c2b68,holder);probe.put(holder,registry)
    for offset,pointer in ((0x4f0,flow),(0x590,env),(0x4a60,mode),(0x360,dummy)):
        probe.put(registry+offset,pointer)
    probe.put(dummy+0x48,dummy+0x100)
    probe.vm.mem_write(env,environment)
    screen,record=Probe.BASE+0x60000,Probe.BASE+0x61000
    probe.run(manager,screen,record,1,0)
    return (probe.get(manager+0x1ef9,1),probe.get(manager+0x1efc,4),probe.get(manager+0x1f00,4))


def original_score_display(contract,totals,visible):
    owner,disp,root,table,rect=(Probe.BASE+n for n in (0x1000,0x2000,0x3000,0x4000,0x5000))
    events=[]
    def cstring(probe,address):
        result=bytearray()
        for i in range(128):
            byte=probe.vm.mem_read(address+i,1)
            if byte==b'\0':return result.decode('ascii')
            result.extend(byte)
        raise AssertionError('unterminated native label')
    def callback(probe,name,args):
        if name.endswith('LocalSkin14GetCurrentTypeEv'):return 0
        if name=='indirect:0xf001':
            events.append(('visibility',cstring(probe,args[1])));return None
        if name=='indirect:0xf002':return rect
        if name.endswith('NodeRectText9SetStrNumEl'):
            events.append(('live',args[1]));return None
        if name.endswith('MovieClip13GotoPlayLabelEPKcb'):
            events.append(('digits',args[0],cstring(probe,args[1])));return None
        if name.endswith('MovieClip10SetVisibleEb'):return None
        if name.endswith('MovieClip10LoadBitmapEPKc'):
            events.append(('bitmap',args[0],cstring(probe,args[1])));return None
        raise AssertionError(name)
    probe=Probe(contract,SCORE,callback)
    probe.put(owner+0x10,root);probe.put(root,table)
    probe.put(table+0x90,0xf001);probe.put(table+0xf0,0xf002)
    clips=[Probe.BASE+0x6000+i*0x100 for i in range(6)]
    for offset,pointer in zip((0xa0,0xa8,0xb0,0xb8,0xc0,0xc8),clips):probe.put(owner+offset,pointer)
    # Named bitmap dependency markers let the original native division/index
    # instructions execute without assuming relocated proprietary pointers.
    for i in range(10):
        pointer=Probe.BASE+0x8000+i*16
        probe.vm.mem_write(pointer,('digit'+str(i)+'\0').encode('ascii'))
        probe.put(0x9497658+i*8,pointer)
    probe.put(disp,2,4);probe.put(disp+4,1,4)
    probe.put(disp+0x2c,visible,1)
    probe.put(disp+0x30,totals[0],4);probe.put(disp+0x34,totals[1],4)
    probe.run(owner,1,disp)
    assert [e[1] for e in events if e[0]=='live']==[2,1]
    assert [e[1] for e in events if e[0]=='visibility']==[
        'scoreTime_aggregate_show' if visible else 'scoreTime_aggregate_off']
    digits=[e[2] for e in events if e[0]=='digits']
    assert digits==['aggregate_disit_2' if n>=10 else 'aggregate_disit_1' for n in totals],digits
    bitmap=[e[2] for e in events if e[0]=='bitmap']
    assert bitmap==['digit'+c for n in totals for c in f'{min(99,n):02}']
    return dict(totals=list(totals),visible=visible,events=events)


def native_probes():
    contract=native_contract()
    rows=[]
    for first,goals in (((3,1),(2,0)),((2,4),(0,3)),((10,12),(2,1))):
        old=original_seed_chain(contract,first,goals,2)
        fixed=original_seed_chain(contract,first[::-1],goals,2)
        expected=(1,first[0]+goals[0],first[1]+goals[1])
        assert fixed==expected,(first,goals,fixed,expected)
        assert old!=expected
        rows.append(dict(first_current=list(first),current=list(goals),old=list(old),fixed=list(fixed)))
    for leg in (0,1):assert original_seed_chain(contract,(0,0),(2,1),leg)[0]==0
    displays=[]
    for totals,visible in (((5,1),1),((12,13),1),((101,120),1),((0,0),0)):
        print('native display probe '+str((totals,visible)),file=sys.stderr,flush=True)
        displays.append(original_score_display(contract,totals,visible))
    print(json.dumps({'state':'native_setter_env_manager_proved','cases':rows,
        'native_display':displays,
        'function_hashes':{name:hashlib.sha256(code).hexdigest() for name,code in contract['code'].items()}},sort_keys=True))


def test_optional_native_setter_conversion_and_manager_aggregate():
    if not (ROOT/'dist/pes21_nx/libUE4.so').is_file():pytest.skip('compatible ignored libUE4.so required')
    for module in ('elftools','unicorn','capstone'):
        if importlib.util.find_spec(module) is None:pytest.skip(module+' required')
    env=os.environ.copy();env.pop('PYTHONFAULTHANDLER',None)
    ran=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--native-probes'],
        cwd=ROOT,env=env,capture_output=True,text=True,timeout=300)
    assert ran.returncode==0,ran.stdout+ran.stderr
    proof=json.loads(ran.stdout)
    assert proof['state']=='native_setter_env_manager_proved' and len(proof['cases'])==3


if __name__=='__main__' and sys.argv[1:]==['--native-probes']:native_probes()
