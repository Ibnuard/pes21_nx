"""Suspended features must not retain active runtime installation paths."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_camera_picker_and_patches_share_the_disabled_gate():
    policy=(ROOT/'source/experimental_features.h').read_text()
    source=(ROOT/'source/ue4_hooks.c').read_text()
    assert '#define PESNX_STADIUM_V2_ENABLED 0' in policy
    assert '#define PESNX_ENTRANCE_CANARY_ENABLED 0' in policy
    assert '#if PESNX_STADIUM_V2_ENABLED\n    {12u, 0u, 1u},' in source
    start=source.index('  if (PESNX_STADIUM_V2_ENABLED) {\n  const char *stadium_active_symbol')
    end=source.index('\n  }',start)
    assert source[start:end].count('hook_arm64(')==3
    assert 'if (PESNX_ENTRANCE_CANARY_ENABLED)\n    install_fixdemo_scene_trace(module);' in source
