"""Exercise the production hydration boundary with uninitialized player copies."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_gameplan_editor import function

ROOT = Path(__file__).resolve().parents[1]


class PrematchHydrationTests(unittest.TestCase):
    def test_lookup_key_survives_donor_copies_and_vector_reordering(self):
        compiler = shutil.which('gcc') or shutil.which('clang')
        if not compiler:
            self.skipTest('Host C compiler required')
        hooks = (ROOT / 'source/ue4_hooks.c').read_text(encoding='utf-8')
        source = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#define debugPrintf(...) ((void)0)
typedef struct { unsigned char bytes[64]; } Player;
typedef struct { uint16_t locator, padding; uint32_t encoded; uint64_t serial;
                 Player copies[2]; uint32_t stamina; } Member;
typedef struct { uint32_t count; Member members[4]; } Squad;
typedef struct { uint32_t player_count; uint32_t player_unique_ids[4]; } ExhibitionMasterRoster;
static ExhibitionMasterRoster roster = {3, {7511, 530066, 162114}};
static uint32_t exhibition_home_team_id = 5738, exhibition_away_team_id = 108;
static Squad squads[2];
static Player database[3];
static uint32_t writes, ignore_setter;
static uint32_t crypt(void) { return 0xa51e71ffu; }
static uint32_t (*exhibition_common_get_crypt_key)(void) = crypt;
static const ExhibitionMasterRoster *exhibition_find_roster(uint32_t team) { return &roster; }
static void *exhibition_squad_edit_get_squad_data(void *e, uint32_t s) { return &squads[s]; }
static uint32_t exhibition_squad_data_get_player_count(void *s) { return ((Squad*)s)->count; }
static void *exhibition_squad_data_get_player_by_index(void *s, const uint32_t *i) { return &((Squad*)s)->members[*i]; }
static int exhibition_roster_player_allowed(const ExhibitionMasterRoster *r, uint32_t id) { return 1; }
static uint64_t exhibition_get_player_id_by_unique_id(const uint32_t *id) { return (uint64_t)*id << 32; }
static unsigned char *exhibition_commonwork_update_player(void *w, uint64_t id) {
 for (unsigned i=0;i<3;i++) if ((uint32_t)(id>>32)==roster.player_unique_ids[i]) return database[i].bytes;
 return 0;
}
static void exhibition_squad_edit_update_player(void *e, void *key, void *p, uint32_t type) {
 if (ignore_setter) return;
 ((Member*)key)->copies[type]=*(Player*)p; writes++;
}
static void *match_squad_data_get_tmpdb_player(void *s, const void *key) {
 return (void *)&((const Member*)key)->copies[0];
}
'''
        source += function(hooks, 'exhibition_refresh_squad_side_player_stats')
        source += r'''
static uint64_t id_of(Player *p) { uint64_t id; memcpy(&id,p->bytes+44,8); return id; }
int main(void) {
 for (unsigned i=0;i<3;i++) {
  uint64_t id=exhibition_get_player_id_by_unique_id(&roster.player_unique_ids[i]);
  memcpy(database[i].bytes+44,&id,8);
 }
 for (unsigned side=0;side<2;side++) {
  squads[side].count=3;
  for(unsigned i=0;i<3;i++) {
   Member *m=&squads[side].members[i];
   unsigned j=(i+1)%3; /* vector order differs from roster */
   /* The match-local locator differs from the master database locator. */
   m->locator=65533+side; m->encoded=roster.player_unique_ids[j]^crypt();
   m->serial=91+i; m->stamina=42+i;
   /* HOME has nonzero placeholders; AWAY has another valid roster identity. */
   uint64_t donor=side ? id_of(&database[(j+1)%3]) : 65533;
   memcpy(m->copies[0].bytes+44,&donor,8);
   m->copies[1]=m->copies[0];
  }
  assert(exhibition_refresh_squad_side_player_stats(0,0,side)==3);
  for(unsigned i=0;i<3;i++) {
   Member *m=&squads[side].members[i];
   uint64_t expected=id_of(&database[(i+1)%3]);
   assert(id_of(&m->copies[0])==expected && id_of(&m->copies[1])==expected);
   assert(m->serial==91+i && m->stamina==42+i && m->locator==65533+side);
  }
  assert(exhibition_refresh_squad_side_player_stats(0,0,side)==3);
 }
 assert(writes==24);
 /* Reject unknown/empty keys and duplicate identities. */
 squads[0].members[0].encoded=999999^crypt();
 squads[0].members[1].encoded=crypt();
 assert(exhibition_refresh_squad_side_player_stats(0,0,0)==1);
 squads[0].members[0]=squads[0].members[2];
 assert(exhibition_refresh_squad_side_player_stats(0,0,0)==1);
 /* A native setter that did not hydrate the copy must not report success. */
 memset(&squads[0].members[0].copies,0,sizeof(squads[0].members[0].copies));
 ignore_setter=1;
 assert(exhibition_refresh_squad_side_player_stats(0,0,0)==0);
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='pes-hydration-') as directory:
            src = Path(directory) / 'test.c'
            exe = Path(directory) / 'test.exe'
            src.write_text(source, encoding='utf-8')
            subprocess.run([compiler, '-std=c11', str(src), '-o', str(exe)], check=True, capture_output=True)
            subprocess.run([str(exe)], check=True, capture_output=True)
