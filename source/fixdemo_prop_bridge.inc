/* Read-only preflight for a future, explicitly opted-in FixDemo prop bridge.
 *
 * NOT a hook installer. No native factory, scene, save, allocator or vtable is
 * changed here. The native renderer only loads boots/backboards as UE static
 * meshes; arbitrary Fox FPKs and skeletal props are not supported by it.
 * CUP/PODIUM adaptation remains OFF until the render-thread/queue ownership,
 * cooked materials/axes and teardown have been validated on the target.
 *
 * ABI observations are specific to Mobile v5.3.0 A279...D187. SHA-256 must be
 * measured from the original local ELF and package, not copied from a marker.
 * Signature reads must use the loader's readable backing, never inaccessible
 * pre-finalize RX pages. Memory snapshots below must be taken at an owned,
 * serialized game-thread boundary; an epoch is not a substitute for a lock.
 */
#ifndef PESNX_FIXDEMO_PROP_BRIDGE_INC
#define PESNX_FIXDEMO_PROP_BRIDGE_INC

#include <stddef.h>
#include <stdint.h>
#include <string.h>

enum { FIXDEMO_PROP_ACTIVATION_VALIDATED = 0 };
enum FixDemoPropKind { FIXDEMO_PROP_NONE, FIXDEMO_PROP_CUP, FIXDEMO_PROP_PODIUM };

typedef struct {
  enum FixDemoPropKind kind;
  const char *descriptor_path;
  const char *runtime_path;
  const char *ue_name; /* AObjectBaseActor prepends /Game/Assets/. */
} FixDemoPropMapping;

static const FixDemoPropMapping fixdemo_prop_mappings[] = {
  {FIXDEMO_PROP_CUP,
   "common/demo/prop/cup_int_hi/cup_int_hi.fpk",
   "common/demo/prop/cup_int_hi/cup_int_hi.xml",
   "FootballNX/FixDemo/cup_int_hi/cup_int_hi.cup_int_hi"},
  {FIXDEMO_PROP_PODIUM,
   "common/demo/fixdemoobj/winners_platform_common/winners_platform_common.fpk",
   "common/demo/fixdemoobj/winners_platform_common/winners_platform_common.xml",
   "FootballNX/FixDemo/platform_cmn/platform_cmn.platform_cmn"},
};

/* Exact, length-delimited identity. No basename, case folding, traversal,
 * #Win alias, .fpk->.xml rewrite or permissive "cup_*" matching at runtime. */
static inline const FixDemoPropMapping *fixdemo_prop_lookup(
    const char *path, size_t length, int descriptor) {
  if (!path || !length || length > 127u) return NULL;
  for (size_t i = 0; i < sizeof(fixdemo_prop_mappings) / sizeof(fixdemo_prop_mappings[0]); ++i) {
    const FixDemoPropMapping *entry = &fixdemo_prop_mappings[i];
    const char *expected = descriptor ? entry->descriptor_path : entry->runtime_path;
    if (length == strlen(expected) && !memcmp(path, expected, length)) return entry;
  }
  return NULL;
}

static const char fixdemo_prop_elf_sha256[] =
    "a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187";
static const char fixdemo_prop_marker_header[] = "PESNX_FIXDEMO_PROPS_V1\npak_sha256=";

static inline int fixdemo_prop_valid_sha256(const char *value, size_t length) {
  int nonzero = 0;
  if (!value || length != 64u) return 0;
  for (size_t i = 0; i < length; ++i) {
    const unsigned char ch = (unsigned char)value[i];
    if (!((ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f'))) return 0;
    nonzero |= ch != '0';
  }
  return nonzero;
}

/* approved_sha is pinned by a separately reviewed release manifest. A marker
 * is never itself authority for the package hash. No package is approved by
 * this file; passing preflight is still not activation permission. */
static inline int fixdemo_prop_package_matches(const char *marker, size_t length,
    const char *measured_sha, size_t measured_length,
    const char *approved_sha, size_t approved_length) {
  const size_t header = sizeof(fixdemo_prop_marker_header) - 1u;
  if (!marker || length != header + 65u ||
      !fixdemo_prop_valid_sha256(measured_sha, measured_length) ||
      !fixdemo_prop_valid_sha256(approved_sha, approved_length)) return 0;
  return !memcmp(marker, fixdemo_prop_marker_header, header) &&
      !memcmp(marker + header, measured_sha, 64u) && marker[header + 64u] == '\n' &&
      !memcmp(measured_sha, approved_sha, 64u);
}

typedef struct {
  const char *symbol;
  uint64_t rva;
  uint32_t offset;
  uint32_t words[8];
} FixDemoPropAbiWindow;

/* Small instruction windows bind the offsets below to the complete ELF hash.
 * They are compatibility fingerprints, not a claim of executed game code. */
static const FixDemoPropAbiWindow fixdemo_prop_abi_windows[] = {
  {"_ZN13FixDemoObject12CreateObjectENS_4TYPEEPKcPN5cobra3And8SkelFileEPNS3_6texlib5ColorE",
   0x7b8d8f8u, 0x98u, {0xb5002596,0x7941d268,0xaa1703e0,0x9103e276,0x7901e268,0x96f15913,0xaa0003e2,0xaa1603e0}},
  {"_Z23FixDemoCorrectModelPathRN5cobra3stl12basic_stringIcNSt6__ndk111char_traitsIcEENS0_9AllocatorIcEEEEb",
   0x7b558f4u, 0xd0u, {0x90005401,0xf00032e2,0x910ad021,0x91027c42,0xaa1303e0,0x96f6023a,0x900032c1,0x91156c21}},
  {"_ZN13FixDemoObjectD1Ev",
   0x7b8d82cu, 0u, {0xa9bf7bf3,0xb000d208,0xaa0003f3,0xf9405c00,0xf9418108,0x91004108,0xf9000268,0xb40000a0}},
  {"_ZN13FixDemoObject9DrawModelEv",
   0x7b8e728u, 0x454u, {0xf9405e60,0xb4000200,0x39405008,0x340001c8,0xf9404668,0x6f00e400,0x910003e1,0x910183e2}},
  {"_ZN4draw10DemoObject6UpdateERKN10Vectormath3Aos7Vector3ERKNS2_4QuatE",
   0x7e226c0u, 0x10u, {0xaa0003f3,0xf9400400,0xb4000300,0xb0000028,0x3dc00040,0x3dc00022,0xbd4f4103,0x3d8003e0}},
  {"_ZN8UEObject8LoadImplEv",
   0x3f013f0u, 0x90u, {0x97e56598,0xf9400668,0xf9010500,0xf9400661,0xf9410420,0x97e5a6fb,0xa9027fff,0xf9400668}},
  {"_ZN16AObjectBaseActor8LoadMeshEPKc",
   0x3effdb0u, 0x104u, {0x97e6d6c7,0x320003e6,0xaa1f03e1,0xaa1403e2,0xaa1f03e3,0x2a1f03e4,0xaa1f03e5,0xaa1f03e7}},
  {"_ZN20UStaticMeshComponent13SetStaticMeshEP11UStaticMesh",
   0x549c5d8u, 0x28u, {0xf942d808,0xeb01011f,0x54002840,0xaa0003f3,0xf9407800,0xf9407675,0xaa0103f4,0xb5000080}},
  {"_ZN20UStaticMeshComponent13SetStaticMeshEP11UStaticMesh",
   0x549c5d8u, 0x70u, {0xaa1303e0,0xf902da74,0x978d73d8,0xaa1303e0,0x97909ea6,0xf9400268,0xaa1303e0,0xf941f108}},
};

typedef int (*FixDemoPropReadSymbol)(void *context, const char *symbol,
    uint32_t offset, unsigned char bytes[32], uint64_t *symbol_rva);

typedef struct {
  const char *elf_sha;
  size_t elf_sha_length;
  unsigned elf_bits, machine, little_endian;
  FixDemoPropReadSymbol read_symbol;
  void *context;
} FixDemoPropAbiEvidence;

static inline int fixdemo_prop_validate_abi(const FixDemoPropAbiEvidence *evidence) {
  if (!evidence || sizeof(uintptr_t) != 8u || evidence->elf_bits != 64u ||
      evidence->machine != 183u || evidence->little_endian != 1u ||
      !evidence->read_symbol || !evidence->elf_sha || evidence->elf_sha_length != 64u ||
      memcmp(evidence->elf_sha, fixdemo_prop_elf_sha256, 64u)) return 0;
  for (size_t i = 0; i < sizeof(fixdemo_prop_abi_windows) / sizeof(fixdemo_prop_abi_windows[0]); ++i) {
    const FixDemoPropAbiWindow *window = &fixdemo_prop_abi_windows[i];
    unsigned char bytes[32];
    uint64_t rva = 0;
    if (!evidence->read_symbol(evidence->context, window->symbol, window->offset, bytes, &rva) ||
        rva != window->rva) return 0;
    for (size_t j = 0; j < 8u; ++j) {
      const uint32_t word = (uint32_t)bytes[4*j] | (uint32_t)bytes[4*j+1] << 8 |
          (uint32_t)bytes[4*j+2] << 16 | (uint32_t)bytes[4*j+3] << 24;
      if (word != window->words[j]) return 0;
    }
  }
  return 1;
}

enum FixDemoPropPreflight {
  FIXDEMO_PROP_NOT_REQUESTED,
  FIXDEMO_PROP_BAD_PACKAGE,
  FIXDEMO_PROP_BAD_ABI,
  FIXDEMO_PROP_VALIDATED_BUT_INACTIVE
};

static inline enum FixDemoPropPreflight fixdemo_prop_preflight(int opt_in,
    const char *marker, size_t length, const char *measured_sha, size_t measured_length,
    const char *approved_sha, size_t approved_length, const FixDemoPropAbiEvidence *abi) {
  if (opt_in != 1) return FIXDEMO_PROP_NOT_REQUESTED;
  if (!fixdemo_prop_package_matches(marker, length, measured_sha, measured_length,
                                   approved_sha, approved_length)) return FIXDEMO_PROP_BAD_PACKAGE;
  if (!fixdemo_prop_validate_abi(abi)) return FIXDEMO_PROP_BAD_ABI;
  return FIXDEMO_PROP_VALIDATED_BUT_INACTIVE;
}

static inline int fixdemo_prop_can_activate(enum FixDemoPropPreflight preflight) {
  return FIXDEMO_PROP_ACTIVATION_VALIDATED && preflight == FIXDEMO_PROP_VALIDATED_BUT_INACTIVE;
}

/* Owner tokens are diagnostic snapshots, never ownership of native memory.
 * Invalidation runs before native destruction; no render pointer is cached. */
typedef struct {
  uintptr_t owner;
  uint64_t epoch;
  enum FixDemoPropKind kind;
} FixDemoPropOwnerToken;

static inline void fixdemo_prop_forget_owner(FixDemoPropOwnerToken *token) {
  if (token) memset(token, 0, sizeof(*token));
}

typedef int (*FixDemoPropReadMemory)(void *context, uintptr_t address, void *output, size_t size);

static inline int fixdemo_prop_read_pointer(FixDemoPropReadMemory read, void *context,
    uintptr_t base, size_t offset, uintptr_t *value) {
  unsigned char bytes[8];
  uint64_t result = 0;
  if (!read || !value || !base || (base & 7u) || offset > UINTPTR_MAX - 7u ||
      base > UINTPTR_MAX - offset - 7u ||
      !read(context, base + offset, bytes, sizeof(bytes))) return 0;
  for (unsigned i = 0; i < 8u; ++i) result |= (uint64_t)bytes[i] << (i * 8u);
  if (!result || (result & 7u)) return 0;
  *value = (uintptr_t)result;
  return 1;
}

/* Native UEObject::IsLoaded only tests Actor!=NULL. Require the actual mesh
 * bound to its StaticMeshComponent as well. Still not proof of render/GPU
 * residency, material correctness, or safe unsynchronized UObject access. */
static inline int fixdemo_prop_mesh_ready(enum FixDemoPropPreflight preflight,
    const FixDemoPropOwnerToken *token, uint64_t current_epoch, int serialized_game_thread,
    FixDemoPropReadMemory read, void *context) {
  uintptr_t demo, model, ue, impl, actor, component, mesh, bound, final_demo;
  const FixDemoPropMapping *mapping = NULL;
  if (preflight != FIXDEMO_PROP_VALIDATED_BUT_INACTIVE || !token || !token->epoch ||
      token->epoch != current_epoch || serialized_game_thread != 1) return 0;
  for (size_t i = 0; i < sizeof(fixdemo_prop_mappings) / sizeof(fixdemo_prop_mappings[0]); ++i)
    if (token->kind == fixdemo_prop_mappings[i].kind) mapping = &fixdemo_prop_mappings[i];
  if (!mapping || !fixdemo_prop_read_pointer(read, context, token->owner, 184u, &demo) ||
      !fixdemo_prop_read_pointer(read, context, demo, 8u, &model) ||
      !fixdemo_prop_read_pointer(read, context, model, 24u, &ue) ||
      !fixdemo_prop_read_pointer(read, context, ue, 8u, &impl) ||
      !fixdemo_prop_read_pointer(read, context, impl, 520u, &actor) ||
      !fixdemo_prop_read_pointer(read, context, actor, 816u, &component) ||
      !fixdemo_prop_read_pointer(read, context, actor, 824u, &mesh) ||
      !fixdemo_prop_read_pointer(read, context, component, 1456u, &bound) || mesh != bound) return 0;
  char name[128];
  const size_t length = strlen(mapping->ue_name) + 1u;
  if (length > sizeof(name) || !read(context, impl, name, length) ||
      memcmp(name, mapping->ue_name, length)) return 0;
  /* Detect replacement during the snapshot. A real backend must additionally
   * own the lifecycle boundary; this check alone does not prevent a race. */
  return fixdemo_prop_read_pointer(read, context, token->owner, 184u, &final_demo) && final_demo == demo;
}

typedef void (*FixDemoPropNativeCreate)(void *, int, const char *, void *, void *);
typedef void (*FixDemoPropNativeDestroy)(void *);

/* Deliberately forwarding-only until the missing backend proof is supplied.
 * Preserve every argument, including skeleton and colors, even for the two
 * allowlisted paths. No file/marker can alter this behavior in this version. */
static inline int fixdemo_prop_forward_create(FixDemoPropNativeCreate original,
    void *owner, int type, const char *path, void *skeleton, void *colors) {
  if (!original) return 0;
  original(owner, type, path, skeleton, colors);
  return 1;
}

static inline int fixdemo_prop_forward_destroy(FixDemoPropNativeDestroy original,
    void *owner, FixDemoPropOwnerToken *token) {
  if (!original) return 0;
  if (token && token->owner == (uintptr_t)owner) fixdemo_prop_forget_owner(token);
  original(owner); /* Preserve native destruction; never free renderer/animation fields here. */
  return 1;
}

#endif
