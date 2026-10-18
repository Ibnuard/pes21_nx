#ifndef PES_GL_UPLOAD_BUDGET_H
#define PES_GL_UPLOAD_BUDGET_H
#include <stdint.h>
#include <string.h>

/* Bound unswapped world loading, not uploads accumulated across live frames.
 * Contexts on an upload thread must not be reset by a different context's swap.
 * A full table fails conservatively (submit), never drops an upload. */
#define NX_UPLOAD_CONTEXTS 8
#define NX_UPLOAD_LIMIT 512u
typedef struct { uintptr_t context; unsigned used, uploads; } NxUploadContext;
typedef struct { NxUploadContext slots[NX_UPLOAD_CONTEXTS]; } NxUploadBudget;
static inline int nx_upload_due(NxUploadBudget *b, uintptr_t context) {
  NxUploadContext *empty = 0;
  for (unsigned i=0; i<NX_UPLOAD_CONTEXTS; ++i) {
    NxUploadContext *s=&b->slots[i];
    if (!s->used) { if (!empty) empty=s; continue; }
    if (s->context!=context) continue;
    if (++s->uploads<NX_UPLOAD_LIMIT) return 0;
    s->uploads=0; return 1;
  }
  if (!empty) return 1;
  *empty=(NxUploadContext){context,1,1}; return 0;
}
static inline void nx_upload_presented(NxUploadBudget *b, uintptr_t context,
                                       int success) {
  if (!success) return;
  for (unsigned i=0; i<NX_UPLOAD_CONTEXTS; ++i)
    if (b->slots[i].used && b->slots[i].context==context)
      b->slots[i].uploads=0;
}
static inline void nx_upload_forget(NxUploadBudget *b, uintptr_t context) {
  for (unsigned i=0; i<NX_UPLOAD_CONTEXTS; ++i)
    if (b->slots[i].used && b->slots[i].context==context)
      memset(&b->slots[i],0,sizeof(b->slots[i]));
}
#endif
