"""Prevent skin-only manifests from reverting the installed cinematic CPK."""
import shutil
import subprocess
from pathlib import Path

import pytest

from test_loose_cpk import cpk
from compose_loose_cpk import compose_manifest, verify_overlay
from prepare_loose_cpk import (FULL_NAMES, PATCH_OBB, digest, extract_full,
                               read_manifest, write_manifest)

ROOT = Path(__file__).resolve().parents[1]
BUILD = '0123456789abcdef'


@pytest.fixture
def packages(tmp_path):
    source = tmp_path / 'source.obb'
    source.write_bytes(cpk({name: cpk({'asset': name.encode()}) for name in FULL_NAMES}))
    base, cinematic, skin = [tmp_path / name for name in ('base', 'cinematic', 'skin')]
    extract_full(source, base, BUILD)
    for root in (cinematic, skin):
        (root / 'LooseCpk').mkdir(parents=True)
    movie = cinematic / 'LooseCpk/dt220_mobile_all.cpk'
    movie.write_bytes(cpk({'asset': b'walkout and trophy scene, different size'}))
    write_manifest(cinematic, compose_manifest(base, {movie.name: movie}))
    appearance = skin / 'LooseCpk/dt200_mobile_all.cpk'
    appearance.write_bytes(cpk({'asset': b'own identity-bound skin selection'}))
    return base, cinematic, skin, appearance


def test_composition_preserves_every_unrelated_current_row_and_does_not_copy_obb(packages):
    base, cinematic, skin, appearance = packages
    old = read_manifest(cinematic)
    merged = compose_manifest(cinematic, {appearance.name: appearance})
    for before, after in zip(old['files'], merged['files']):
        if before['name'] != appearance.name:
            assert after == before
    write_manifest(skin, merged)
    report = verify_overlay(merged, [skin, cinematic, base])
    assert len(report['files']) == 24
    assert report['all_cpk_hashes_verified']
    assert not (skin / PATCH_OBB).exists() and not (cinematic / PATCH_OBB).exists()
    assert read_manifest(cinematic) == old


def test_old_skin_manifest_reproduces_the_cinematic_mismatch(packages):
    base, cinematic, skin, appearance = packages
    bad = compose_manifest(base, {appearance.name: appearance})
    with pytest.raises(ValueError, match='dt220_mobile_all.cpk'):
        verify_overlay(bad, [skin, cinematic, base])


def test_overlay_does_not_fall_back_past_a_corrupt_higher_priority_file(packages):
    base, cinematic, skin, appearance = packages
    merged = compose_manifest(cinematic, {appearance.name: appearance})
    (skin / 'LooseCpk/dt220_mobile_all.cpk').write_bytes(b'CPK corrupt')
    with pytest.raises(ValueError, match='dt220_mobile_all.cpk'):
        verify_overlay(merged, [skin, cinematic, base])


def test_rejects_unapproved_names_and_bad_replacement_before_composition(packages):
    base, _, _, appearance = packages
    with pytest.raises(ValueError, match='approved'):
        compose_manifest(base, {'../other.cpk': appearance})
    appearance.write_bytes(b'bad')
    with pytest.raises((ValueError, RuntimeError)):
        compose_manifest(base, {appearance.name: appearance})


@pytest.fixture(scope='module')
def native_validator(tmp_path_factory):
    compiler = shutil.which('gcc') or shutil.which('clang')
    if not compiler:
        pytest.skip('Host C compiler unavailable')
    work = tmp_path_factory.mktemp('native-loose-composition')
    source = work / 'validate.c'
    source.write_text('''#include <stdio.h>
#include "loose_cpk.h"
int main(void) {
  char error[256] = {0};
  int mode = pes_loose_cpk_init("0123456789abcdef", 1, error, sizeof(error));
  printf("mode=%d %s\\n", mode, error);
  return mode == 2 ? 0 : 1;
}
''')
    executable = work / 'validate.exe'
    subprocess.run([compiler, '-std=c11', '-I', str(ROOT / 'source'), str(source),
                    str(ROOT / 'source/loose_cpk.c'), '-o', str(executable)],
                   check=True, capture_output=True)
    return executable


def test_actual_native_validation_rejects_old_manifest_then_accepts_composed_set(
        packages, tmp_path, native_validator):
    base, cinematic, skin, appearance = packages
    installed = tmp_path / 'installed'
    # These are tiny synthetic test archives, never proprietary OBB fixtures.
    shutil.copytree(base, installed)
    shutil.copytree(cinematic, installed, dirs_exist_ok=True)
    shutil.copy2(appearance, installed / 'LooseCpk' / appearance.name)
    bad = compose_manifest(base, {appearance.name: appearance})
    write_manifest(installed, bad)
    failed = subprocess.run([str(native_validator)], cwd=installed, capture_output=True, text=True)
    assert failed.returncode == 1 and 'dt220_mobile_all.cpk' in failed.stdout
    write_manifest(installed, compose_manifest(cinematic, {appearance.name: appearance}))
    accepted = subprocess.run([str(native_validator)], cwd=installed, capture_output=True, text=True)
    assert accepted.returncode == 0 and 'mode=2' in accepted.stdout
    assert verify_overlay(read_manifest(installed), [installed])['all_cpk_hashes_verified']
