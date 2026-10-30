"""Actual C selector and bounded native-adapter tests. No device execution claim."""
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def corner_binary(tmp_path_factory):
    cc=shutil.which('gcc') or shutil.which('clang')
    if not cc:pytest.skip('host C compiler required')
    out=tmp_path_factory.mktemp('corner-v69')/'corner.exe'
    subprocess.run([cc,'-std=c11','-Wall','-Wextra','-Werror','-pthread',
        '-I',(ROOT/'source').as_posix(),(ROOT/'tests/corner_tactics_cases.c').as_posix(),
        (ROOT/'source/corner_tactics.c').as_posix(),'-o',out.as_posix()],check=True,capture_output=True,text=True)
    return out

@pytest.mark.parametrize('mode',[1,2,3])
@pytest.mark.parametrize('direction',range(4))
def test_native_option_mapping_and_no_input_leak(corner_binary,mode,direction):
    subprocess.run([str(corner_binary),'choice',str(mode),str(direction)],check=True,capture_output=True,text=True)

@pytest.mark.parametrize('case',['cancel','stale','epoch','pause','disconnect',
    'two-pads','diagonal','restart-ended','reset','ordinary-play','first-ready'])
def test_corner_lifetime_and_per_pad_ownership(corner_binary,case):
    subprocess.run([str(corner_binary),case],check=True,capture_output=True,text=True)

def test_integration_keeps_taker_and_v67_boundary():
    shim=(ROOT/'source/android_shim.c').read_text()
    assert 'if(!(corner_input_p1&FNX_CORNER_CAPTURE))' in shim
    assert 'if(!(corner_input_p2&FNX_CORNER_CAPTURE))' in shim
    assert 'corner_capture_p1 ? 0 : native_buttons' in shim
    assert 'corner_capture_p2 ? 0 : native_buttons_p2' in shim
    assert 'const u64 reserved_full = HidNpadButton_Right | HidNpadButton_Minus;' in shim
    hooks=(ROOT/'source/ue4_hooks.c').read_text()
    assert 'exhibition_rebase_prepared_matchplan()' in hooks
    adapter=(ROOT/'source/corner_tactics_native.inc').read_text()
    assert 'memcpy((char *)unit+0x19,&option,1)' in adapter
    assert 'memcpy((char *)ai' not in adapter
    assert 'corner_native_same(&context,&corner_native_last[pad])' in adapter

@pytest.fixture(scope='module')
def native_binary(tmp_path_factory):
    cc=shutil.which('gcc') or shutil.which('clang')
    if not cc:pytest.skip('host C compiler required')
    out=tmp_path_factory.mktemp('corner-native-v69')/'native.exe'
    subprocess.run([cc,'-std=c11','-Wall','-Wextra','-Werror','-pthread',
        '-I',(ROOT/'source').as_posix(),(ROOT/'tests/corner_native_cases.c').as_posix(),
        (ROOT/'source/corner_tactics.c').as_posix(),'-o',out.as_posix()],check=True,capture_output=True,text=True)
    return out

@pytest.mark.parametrize('case',['commands','role-switch','not-ready','match-generation',
    'single-player','abi-fallback','out-of-play','restart-kinds',
    'conflicting-restart','other-restart-list','nameplate-start',
    'nameplate-start-during-native','nameplate-return'])
def test_actual_native_adapter(native_binary,case):
    subprocess.run([str(native_binary),case],check=True,capture_output=True,text=True)

@pytest.fixture(scope='module')
def hid_binary(tmp_path_factory):
    cc=shutil.which('gcc') or shutil.which('clang')
    if not cc:pytest.skip('host C compiler required')
    out=tmp_path_factory.mktemp('corner-hid-v69')/'hid.exe'
    from test_gameplan_editor import function
    shim=(ROOT/'source/android_shim.c').read_text()
    cases=(ROOT/'tests/corner_hid_cases.c').read_text()
    mapping='typedef enum {CONTROLLER_PROFILE_FULL,CONTROLLER_PROFILE_SINGLE_LEFT,CONTROLLER_PROFILE_SINGLE_RIGHT} ControllerProfile;\n'+function(shim,'controller_profile_map_buttons')+'\n'
    cases=cases.replace('#include "corner_tactics_hid.inc"',mapping+'#include "corner_tactics_hid.inc"')
    source=out.with_suffix('.c');source.write_text(cases)
    subprocess.run([cc,'-std=c11','-Wall','-Wextra','-Werror','-pthread',
        '-I',(ROOT/'source').as_posix(),source.as_posix(),
        (ROOT/'source/corner_tactics.c').as_posix(),'-lm','-o',out.as_posix()],check=True,capture_output=True,text=True)
    return out

@pytest.mark.parametrize('case',['full-right','single-hold','single-short-two-pads','single-mapping','cancel','short-page','nameplate-start'])
def test_actual_hid_adapter(hid_binary,case):
    subprocess.run([str(hid_binary),case],check=True,capture_output=True,text=True)

@pytest.mark.parametrize('name,white',[('b','main_menu_button_b'),('x','switch_button_x')])
def test_dark_helper_derivatives_preserve_silhouette_and_are_registered(name,white):
    image=pytest.importorskip('PIL.Image')
    dark_path=ROOT/'data'/f'switch_button_{name}_dark.bin'
    with image.open(dark_path) as dark,image.open(ROOT/'data'/f'{white}.bin') as original:
        assert dark.size==original.size==(80,80)
        assert dark.getchannel('A').tobytes()==original.getchannel('A').tobytes()
        pixels=list(dark.convert('RGBA').getdata())
        assert sum(a==255 and r<40 and g<50 and b<75 for r,g,b,a in pixels)>1500
        assert sum(a==255 and r>230 and g>230 and b>230 for r,g,b,a in pixels)>80
    assert dark_path.read_bytes()==(ROOT/'art/SwitchButton'/f'{name.upper()}_Button_Dark.png').read_bytes()
    header=(ROOT/'source/switch_button_assets.h').read_text()
    assert f'X({name}_dark, "{name.upper()}_DARK")' in header
