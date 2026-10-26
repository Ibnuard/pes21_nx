"""Catalog readers preserve identity/asset bindings without creating a career."""
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_immutable_catalog_identity_and_unpaired_defaults():
    cc = shutil.which('gcc')
    if not cc:
        pytest.skip('Host C compiler unavailable')
    fixture = '''
#define ML_CATALOG_CONTENT_ID "synthetic-content"
#define ML_CATALOG_PAIR_ID "synthetic-pair"
static const MlCatalogPlayer ml_catalog_players[] = {
  {900u, 41u, 77u, 101u, 63u, 0u, 1u, "Synthetic Keeper"},
  {12u, 409u, 808u, 101u, 69u, 3u, 2u, "Synthetic Defender"},
  {0x80000003u, 14u, 99u, 202u, 81u, 12u, 9u, "Local Player"}
};
#define ML_CATALOG_PLAYER_COUNT 3u
'''
    harness = '''
#include "master_league_catalog.h"
#include <assert.h>
#include <stddef.h>
#include <string.h>
/* Any reader accidentally writing/importing player state fails this test. */
int ml_add_player(MasterLeague *c, uint32_t club, const MlPlayer *p) {
  (void)c; (void)club; (void)p; assert(0); return 0;
}
int main(void) {
  assert(!strcmp(ml_catalog_manager_binding_id(), "unpaired"));
  assert(!ml_catalog_has_real_portrait(0u));
  assert(!ml_catalog_has_real_portrait(134931u));
  assert(!ml_catalog_has_real_portrait(0x80000003u));
  assert(!ml_catalog_player_at(UINT32_MAX));
  assert(!ml_catalog_find_identity(0u));
  assert(!ml_catalog_find_identity(123456u));
#ifdef SYNTHETIC_CATALOG
  assert(ml_catalog_player_count() == 3u);
  assert(!strcmp(ml_catalog_content_id(), "synthetic-content"));
  assert(!strcmp(ml_catalog_pair_id(), "synthetic-pair"));
  const MlCatalogPlayer *p=ml_catalog_player_at(1u);
  assert(p && p->identity == 12u && p->native_id == 409u);
  assert(p->portrait_id == 808u && p->club == 101u);
  assert(p->overall == 69u && p->position == 3u && p->shirt == 2u);
  assert(!strcmp(p->name, "Synthetic Defender"));
  assert(ml_catalog_find_identity(12u) == p);
  assert(ml_catalog_find_identity(900u) == ml_catalog_player_at(0u));
  assert(ml_catalog_find_identity(0x80000003u) == ml_catalog_player_at(2u));
  assert(!ml_catalog_player_at(3u));
  /* Looking up an asset/native key must not impersonate canonical identity. */
  assert(!ml_catalog_find_identity(409u) && !ml_catalog_find_identity(808u));
#else
  assert(ml_catalog_player_count() == 0u);
  assert(!ml_catalog_player_at(0u));
  assert(!ml_catalog_find_identity(1u));
  assert(!strcmp(ml_catalog_content_id(), "unpaired"));
#endif
  return 0;
}
'''
    with tempfile.TemporaryDirectory() as directory:
        stage = Path(directory)
        (stage/'fixture.inc').write_text(fixture, encoding='utf-8')
        (stage/'catalog_test.c').write_text(harness, encoding='utf-8')
        for synthetic in (False, True):
            command = [cc, '-std=c11', '-Wall', '-Wextra', '-Werror',
                       '-I', str(ROOT/'source'), '-I', str(stage)]
            if synthetic:
                command += ['-DSYNTHETIC_CATALOG', '-DML_CATALOG_INCLUDE=<fixture.inc>']
            command += [str(stage/'catalog_test.c'),
                        str(ROOT/'source/master_league_catalog.c'),
                        '-o', str(stage/'catalog_test.exe')]
            subprocess.run(command, cwd=stage, check=True)
            subprocess.run([str(stage/'catalog_test.exe')], cwd=stage, check=True)
