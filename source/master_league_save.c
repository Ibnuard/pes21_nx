#include "master_league.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#ifdef _WIN32
#include <direct.h>
#endif

#define ML_SAVE_MAGIC 0x314c4d46u /* FML1 */
#define ML_SAVE_VERSION 1u
typedef struct { uint32_t magic, version, size, sequence, checksum; } MlSaveHeader;

static uint32_t ml_checksum(const MasterLeague *career) {
  const unsigned char *p = (const unsigned char *)career;
  uint32_t value = 2166136261u;
  for (size_t i=0; i<sizeof(*career); i++) value = (value ^ p[i]) * 16777619u;
  return value;
}
static void ml_save_path(uint32_t slot, uint32_t copy, char path[80]) {
  snprintf(path, 80, "SaveData/footballnx_master_league_%u_%c.bin",
           slot + 1u, copy ? 'b' : 'a');
}
static int ml_read_copy(uint32_t slot, uint32_t copy, const char *content,
                         MasterLeague *out, uint32_t *sequence) {
  char path[80]; ml_save_path(slot, copy, path);
  FILE *file = fopen(path, "rb");
  if (!file) return 0;
  MlSaveHeader header;
  const int read = fread(&header, 1, sizeof(header), file) == sizeof(header) &&
      header.magic == ML_SAVE_MAGIC && header.version == ML_SAVE_VERSION &&
      header.size == sizeof(*out) &&
      fread(out, 1, sizeof(*out), file) == sizeof(*out);
  const int end = fgetc(file) == EOF, closed = fclose(file) == 0;
  if (!read || !end || !closed || header.checksum != ml_checksum(out) ||
      !ml_valid(out) || (content && strcmp(content, out->content_id))) return 0;
  *sequence = header.sequence;
  return 1;
}
int ml_save_read(uint32_t slot, const char *content, MasterLeague *out) {
  if (slot >= ML_SAVE_SLOTS || !content || !out) return 0;
  MasterLeague *candidate = malloc(sizeof(*candidate));
  MasterLeague *best = malloc(sizeof(*best));
  if (!candidate || !best) { free(candidate); free(best); return 0; }
  int found = 0; uint32_t best_seq=0u;
  for (uint32_t copy=0; copy<2u; copy++) {
    uint32_t seq=0u;
    if (ml_read_copy(slot,copy,content,candidate,&seq) && (!found || seq>best_seq)) {
      *best=*candidate; best_seq=seq; found=1;
    }
  }
  if (found) *out=*best; /* Failure must not mutate the running career. */
  free(candidate); free(best);
  return found;
}
int ml_save_write(uint32_t slot, const MasterLeague *career) {
  if (slot >= ML_SAVE_SLOTS || !ml_valid(career)) return 0;
#ifdef _WIN32
  if (_mkdir("SaveData") != 0 && errno != EEXIST) return 0;
#else
  if (mkdir("SaveData",0777) != 0 && errno != EEXIST) return 0;
#endif
  MasterLeague *verify = malloc(sizeof(*verify));
  if (!verify) return 0;
  uint32_t seq[2]={0};
  const int a=ml_read_copy(slot,0u,NULL,verify,&seq[0]);
  const int b=ml_read_copy(slot,1u,NULL,verify,&seq[1]);
  const uint32_t copy=!a ? 0u : !b ? 1u : seq[0] <= seq[1] ? 0u : 1u;
  const uint32_t sequence=(seq[0]>seq[1] ? seq[0] : seq[1])+1u;
  if (!sequence) { free(verify); return 0; }
  const MlSaveHeader header={ML_SAVE_MAGIC,ML_SAVE_VERSION,sizeof(*career),
                             sequence,ml_checksum(career)};
  char path[80]; ml_save_path(slot,copy,path);
  FILE *file=fopen(path,"wb");
  if (!file) { free(verify); return 0; }
  const int written=fwrite(&header,1,sizeof(header),file)==sizeof(header) &&
      fwrite(career,1,sizeof(*career),file)==sizeof(*career);
  const int flushed=fflush(file)==0, closed=fclose(file)==0;
  uint32_t verified_seq=0u;
  const int valid=written && flushed && closed &&
      ml_read_copy(slot,copy,career->content_id,verify,&verified_seq) &&
      verified_seq==sequence;
  free(verify);
  return valid;
}
