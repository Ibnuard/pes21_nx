#ifndef PESNX_PLAYER_COMMENTARY_TYPES_H
#define PESNX_PLAYER_COMMENTARY_TYPES_H
#include <stddef.h>
#include <stdint.h>
#define PC_BANK_MAX_PLAYERS 80u
#define PC_BANK_MAX_CUES 160u
#define PC_BANK_MAX_HEADERS 187u
#define PC_BANK_MAX_BYTES (8u * 1024u * 1024u)
#define PC_BANK_MAX_AUDIO (2u * 1024u * 1024u)
#define PC_BANK_MAX_SCRATCH (18u * 1024u * 1024u)
enum { PC_OWNER_HOLD=0, PC_OWNER_NATIVE=1, PC_OWNER_CANARY=2,
       PC_OWNER_NEW=3, PC_OWNER_LABEL_HOLD=4, PC_OWNER_NO_P0=5 };
typedef struct {
  uint32_t base_id, native_id;
  const char *fingerprint, *row_sha256;
  uint32_t status, cue_first, cue_count;
} PcBankOwner;
typedef struct {
  uint32_t owner_index, type;
  const char *name, *asset;
  uint32_t bytes, duration_ms, encode_type, channels, loop_flag, rate, samples;
  uint64_t payload_fnv, header_fnv;
} PcBankCue;
typedef struct {
  const char *runtime_pair;
  uint32_t base_bytes, owner_count, cue_count, baseline_header_count;
  uint64_t base_fnv;
  const PcBankOwner *owners;
  const PcBankCue *cues;
  const uint64_t *baseline_headers;
} PcBankCatalog;
typedef struct {
  void *data;
  uint32_t size, cue_count, header_count, player_count;
  uint64_t headers[PC_BANK_MAX_HEADERS];
  const PcBankOwner *players[PC_BANK_MAX_PLAYERS];
  const PcBankCue *cues[PC_BANK_MAX_CUES];
  uint16_t cue_indices[PC_BANK_MAX_CUES];
  size_t scratch_peak;
} PcBankResult;
/* Reader returns an owned malloc allocation, exact bytes, or NULL. The builder
 * frees each recording before reading another. No archive-wide allocation. */
typedef void *(*PcBankRead)(void *, const char *, size_t, size_t *);
#endif
