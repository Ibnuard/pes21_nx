#ifndef __UE4_HOOKS_H__
#define __UE4_HOOKS_H__

#include "so_util.h"

#define PES_MOBILE_CONTROL_UNKNOWN 0
#define PES_MOBILE_CONTROL_OFFENSE 1
#define PES_MOBILE_CONTROL_DEFENSE 2

void install_ue4_hooks(so_module *module);
void cobra_pad_set_input(uint32_t buttons, int32_t up, int32_t down,
                         int32_t left, int32_t right, int connected);
uint32_t pes_mobile_control_context(int *mode);
int pes_mobile_control_active_mode(void);

#endif
