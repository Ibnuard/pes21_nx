#ifndef __UE4_HOOKS_H__
#define __UE4_HOOKS_H__

#include "so_util.h"

void install_ue4_hooks(so_module *module);
void cobra_pad_set_input(uint32_t buttons, int32_t up, int32_t down,
                         int32_t left, int32_t right, int connected);

#endif
