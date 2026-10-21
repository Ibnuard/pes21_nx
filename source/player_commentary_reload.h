#ifndef PESNX_PLAYER_COMMENTARY_RELOAD_H
#define PESNX_PLAYER_COMMENTARY_RELOAD_H

#include <stdint.h>
#include <string.h>
#include "player_commentary_types.h"

#define PC_RELOAD_SIDE_PLAYERS 40u
#define PC_RELOAD_LOAD_LABEL 4u
#define PC_RELOAD_BANK_KIND 29u
#define PC_RELOAD_MAX_BORROWS 4u
#define PC_RELOAD_DEFAULT_TIMEOUT_MS UINT64_C(30000)
#define PC_RELOAD_MAX_TIMEOUT_MS UINT64_C(120000)
#define PC_RELOAD_INITIALIZED UINT32_C(0x50435231)

/* The audited native functions use W0=label/kind, X1=out for GetMountID.
 * GetMountID uses the loader's globals/mutex, not a this/GetInstance argument.
 * Request's return is NOT successful-mount proof. Bind only admitted RX symbols
 * with the exact guards below, then issue label 4 through the callbacks. */
typedef int32_t (*PcReloadNativeRequest)(uint32_t);
typedef uint32_t (*PcReloadNativeBusy)(uint32_t);
typedef int32_t (*PcReloadNativeMountId)(uint32_t, int16_t *);
#define PC_RELOAD_REQUEST_GUARD \
  {UINT32_C(0xf81f0ffe),UINT32_C(0x900145a8),UINT32_C(0xf946f508),UINT32_C(0x39400108)}
#define PC_RELOAD_BUSY_GUARD \
  {UINT32_C(0xa9bf7bf3),UINT32_C(0xb0014588),UINT32_C(0xf946f508),UINT32_C(0x39400108)}
#define PC_RELOAD_MOUNT_ID_GUARD \
  {UINT32_C(0xa9be53f5),UINT32_C(0xa9017bf3),UINT32_C(0x900145c8),UINT32_C(0xf9475908)}

/* All arrays are owned values. Only catalog/owner references point elsewhere:
 * they must reference the immutable compiled catalog for the whole runtime.
 * Preserve the ACTUAL full carriers, including their session locator bits.
 * Unknown owners remain NULL/generic holds; never invent an identity by ID. */
typedef struct {
  const PcBankCatalog *catalog;
  char runtime_pair[17];
  uint64_t generation, selection_key;
  uint32_t logical_team[2], physical_team[2], side_count[2];
  uint32_t native_ids[2][PC_RELOAD_SIDE_PLAYERS];
  uint64_t carriers[2][PC_RELOAD_SIDE_PLAYERS];
  uint32_t ids[PC_BANK_MAX_PLAYERS], count, held_count;
  const PcBankOwner *owners[PC_BANK_MAX_PLAYERS];
} PcSelection;

enum {
  PC_RELOAD_IDLE=0, PC_RELOAD_PREPARING=1, PC_RELOAD_WAITING=2,
  PC_RELOAD_TERMINAL=3, PC_RELOAD_DRAINING=4
};
enum {
  PC_RELOAD_MOUNT_SELECTED=1, PC_RELOAD_MOUNT_V53=2,
  PC_RELOAD_MOUNT_ORIGINAL=3, PC_RELOAD_MOUNT_FAILED=4
};
enum {
  PC_RELOAD_REASON_NONE=0, PC_RELOAD_REASON_SELECTED=1,
  PC_RELOAD_REASON_FALLBACK=2, PC_RELOAD_REASON_PREPARE_FAILED=3,
  PC_RELOAD_REASON_REQUEST_UNAVAILABLE=4, PC_RELOAD_REASON_LOADER_UNAVAILABLE=5,
  PC_RELOAD_REASON_MOUNT_FAILED=6, PC_RELOAD_REASON_MOUNT_MISSING=7,
  PC_RELOAD_REASON_MOUNT_ID=8, PC_RELOAD_REASON_TIMEOUT=9,
  PC_RELOAD_REASON_CANCELLED=10, PC_RELOAD_REASON_STALE_PLAY=11,
  PC_RELOAD_REASON_DISPATCH_FAILED=12, PC_RELOAD_REASON_PRIOR_LOAD_BUSY=13
};
enum { PC_RELOAD_REJECTED=-1, PC_RELOAD_BLOCKED=0, PC_RELOAD_STARTED=1 };

typedef struct {
  /* Callbacks except native mount borrow/report/release run on the serialized
   * menu/game thread. No callback is invoked while the short policy lock is held.
   * prepare must validate/build a fresh bank; discard frees its data allocation.
   * A request return of 1 means the guarded Request(4) was ISSUED, not loaded. */
  int (*prepare)(void *, const PcSelection *, PcBankResult *);
  void (*discard)(void *, PcBankResult *);
  int (*request)(void *, uint32_t);
  int (*busy)(void *, uint32_t, int *);
  int (*mount_id)(void *, uint32_t, int16_t *);
  int (*play_valid)(void *, const PcSelection *, uint64_t);
  int (*dispatch)(void *, const PcSelection *, uint64_t, uint32_t);
  void (*release_loading)(void *, uint64_t, uint64_t, uint32_t, int);
  /* Explicit admission only for a PROVED v53/original mount reported for this
   * generation. Failures/timeouts never silently dispatch an unproved bank. */
  uint32_t allow_native_fallback;
} PcReloadOps;

typedef struct {
  const PcBankResult *bank;
  const PcSelection *selection;
  uint64_t generation, ticket;
  uint32_t slot;
} PcReloadBorrow;

typedef struct {
  PcSelection selection;
  PcBankResult prepared;
  PcReloadOps ops;
  void *context;
  uint64_t next_generation, next_ticket, intent, started_ms, timeout_ms;
  uint64_t tickets[PC_RELOAD_MAX_BORROWS];
  uint32_t initialized, lock, phase, prepared_live, borrowers, request_issued;
  uint32_t mount_reported, mount_outcome, terminal_reason, notified, finishing;
  int16_t reported_mount_id;
} PcReload;

/* Include player_commentary_reload.inc once in the implementation TU.
 * begin/tick/cancel are game-thread serialized. borrow/report/release are the
 * only cross-thread APIs; a ticket pins the immutable preparation until release.
 * Root owns each fresh per-mount copy and all of its mounted header/lookup rows.
 * STARTED owns exactly one release_loading callback (possibly synchronous on
 * rejection). BLOCKED/REJECTED acquire no intent/loading ownership: the caller
 * must keep/restore its usable hub and must not dispatch a duplicate Play. */
static inline int pc_selection_build(PcSelection *, const PcBankCatalog *,
    const char *, const uint32_t[2], const uint32_t[2],
    const uint32_t[2][PC_RELOAD_SIDE_PLAYERS],
    const uint64_t[2][PC_RELOAD_SIDE_PLAYERS], const uint32_t[2]);
static inline int pc_reload_init(PcReload *, const PcReloadOps *, void *, uint64_t);
static inline int pc_reload_begin(PcReload *, const PcSelection *, uint64_t, uint64_t);
static inline void pc_reload_tick(PcReload *, uint64_t);
static inline void pc_reload_cancel(PcReload *);
static inline uint32_t pc_reload_phase(const PcReload *);
static inline int pc_reload_borrow(PcReload *, PcReloadBorrow *);
static inline int pc_reload_report(PcReload *, const PcReloadBorrow *, int16_t, uint32_t);
static inline int pc_reload_release(PcReload *, const PcReloadBorrow *);

#endif
