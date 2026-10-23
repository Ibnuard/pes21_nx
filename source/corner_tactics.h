#ifndef FOOTBALLNX_CORNER_TACTICS_H
#define FOOTBALLNX_CORNER_TACTICS_H
#include <stdint.h>

enum { FNX_CORNER_NONE, FNX_CORNER_ATTACK, FNX_CORNER_SHORT,
       FNX_CORNER_DEFENCE };
enum { FNX_CORNER_UP=1, FNX_CORNER_RIGHT=2, FNX_CORNER_DOWN=4,
       FNX_CORNER_LEFT=8, FNX_CORNER_BACK=16, FNX_CORNER_PAGE=32,
       FNX_CORNER_OTHER=64 };
enum { FNX_CORNER_CAPTURE=1, FNX_CORNER_AVAILABLE=2 };
typedef struct {
  uint32_t available, open, mode, short_allowed, current;
  uint32_t submitted, consumed;
} FnxCornerView;
/* Model thread publishes only scalar state. No borrowed engine pointer leaves
 * the native adapter. Epoch belongs to the actual match/restart/controller. */
void fnx_corner_publish(uint32_t pad, uint64_t epoch, uint32_t mode,
    int short_allowed, uint32_t normal, uint32_t short_choice,
    uint32_t defence, uint64_t now);
void fnx_corner_reset(void);
uint32_t fnx_corner_input(uint32_t pad, uint64_t now, int allowed,
    int connected, uint32_t buttons, int axes_neutral);
int fnx_corner_take(uint32_t pad, uint64_t epoch, uint64_t now,
                    uint32_t *command, uint8_t *option);
void fnx_corner_view(uint32_t pad, uint64_t now, FnxCornerView *out);
const char *fnx_corner_label(uint32_t mode, uint32_t direction);
#endif
