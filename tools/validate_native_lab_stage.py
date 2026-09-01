"""Verify the test runtime retains the accepted v9 features and v14 pitch."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def function(text, name):
    match = re.search(r'\b'+re.escape(name)+r'\([^;{}]*\)\s*\{', text)
    assert match, name
    start = match.end()-1
    depth = 0
    for end in range(start, len(text)):
        depth += (text[end] == '{') - (text[end] == '}')
        if not depth:
            return text[start:end+1]
    raise AssertionError(name+' has no end')


def validate(baseline, runtime, pitch, marker):
    changed = []
    allowed = {'android_shim.c', 'cobra_pad_hook.s', 'ue4_hooks.c',
               'ue4_hooks.h', 'overlay.c'}
    before_files = {p.name for p in (baseline/'source').iterdir() if p.is_file()}
    after_files = {p.name for p in (runtime/'source').iterdir() if p.is_file()}
    assert after_files-before_files == {'native_pad_lab.inc'}
    for previous in (baseline/'source').iterdir():
        if not previous.is_file():
            continue
        current = runtime/'source'/previous.name
        assert current.is_file(), previous.name
        if current.read_bytes() != previous.read_bytes():
            assert previous.name in allowed, previous.name
            changed.append(previous.name)
    for previous in (baseline/'data').rglob('*'):
        if previous.is_file():
            assert digest(previous) == digest(runtime/previous.relative_to(baseline))
    for name in ('Makefile', 'build-wsl.ps1', 'icon.jpg'):
        assert digest(baseline/name) == digest(runtime/name), name
    before = (baseline/'source/ue4_hooks.c').read_text(encoding='utf-8')
    after = (runtime/'source/ue4_hooks.c').read_text(encoding='utf-8')
    preserved = ('pes_inplay_ball_position_broadcast', 'ue4_tickrate_clamp',
                 'pes_match_visual_model_action', 'pes_match_button_setplay_update',
                 'pes_match_button_setplay_need_disp',
                 'pes_match_button_setplay_touch_sub')
    for name in preserved:
        assert function(before,name) == function(after,name), name
    overlay_before = (baseline/'source/overlay.c').read_text(encoding='utf-8')
    overlay = (runtime/'source/overlay.c').read_text(encoding='utf-8')
    # The entire accepted helper drawing batch, not just its color constants.
    begin = overlay_before.index('  if (setplay_helper_text_quads) {',
                                  overlay_before.index('  const int text_quads'))
    end = overlay_before.index('  // restore the two attrib arrays', begin)
    assert overlay_before[begin:end] in overlay
    assert 'PRESS A TO START' in overlay
    assert marker in overlay
    assert 'HidNpadIdType_No2' in (runtime/'source/android_shim.c').read_text(
        encoding='utf-8')
    assert '_ZN9matchPlan4Data10SetPadPortE8HomeAwayj' in after
    assert 'exhibition_matchplan_set_pad_port(data, 0, 0)' in after
    assert 'exhibition_matchplan_set_pad_port(data, 1, 1)' in after
    assert 'PLAYER CURSOR' in after
    assert 'exhibition_migration.inc' not in after # Do not rebase roster code.
    for name in ('config.c','config.h','match_visual_policy.h','friend_press.inc',
                 'main.c','imports.c','android_mmap.c','so_util.c'):
        assert digest(baseline/'source'/name) == digest(runtime/'source'/name), name
    hook_asm = (runtime/'source/cobra_pad_hook.s').read_text(encoding='utf-8')
    assert 'pes_match_cursor_info_from_tmpdb_hook' in hook_asm
    assert 'bl pes_match_cursor_info_ready' in hook_asm
    assert digest(pitch) == '152cedb75b306ea92456219d68fda51e37767f45c3fe3b3b7edc21ea284b53d9'
    nro = runtime/'pes21_nx.nro'
    payload = nro.read_bytes()
    assert payload[16:20] == b'NRO0'
    assert marker.encode('ascii') in payload
    assert b'PLAYER CURSOR' in payload and b'PRESS A TO START' in payload
    return {'runtime':str(runtime), 'baseline':str(baseline),
            'changed_existing_sources': changed, 'preserved_function_bodies':preserved,
            'all_other_source_and_data_equal_baseline':True,
            'helper_palette_batch_equal_baseline':True,
            'native_2p_scope_validated':True,
            'pitch_v14_unchanged':True,
            'nro_bytes':len(payload), 'nro_sha256':digest(nro),
            'diagnostics':False, 'perf_trace':False, 'switch_tested':False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--pitch',type=Path,required=True)
    parser.add_argument('--marker',default='NATIVE SETPLAY V4')
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    report = validate(args.baseline,args.runtime,args.pitch,args.marker)
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
