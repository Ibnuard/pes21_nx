/* config.h -- global configuration and config file handling
 *
 * Copyright (C) 2021 fgsfds, Andy Nguyen
 *
 * This software may be modified and distributed under the terms
 * of the MIT license.  See the LICENSE file for details.
 */

#ifndef __CONFIG_H__
#define __CONFIG_H__

// libUE4 plus the two Konami support libraries occupy about 159 MiB after ELF
// loading. Leave headroom for alignment and future binary variants.
#define MEMORY_SO_MB 224

#define AVS_SO_NAME "libavs2-core.so"
#define AFP_SO_NAME "libafp-core.so"
#define UE4_SO_NAME "libUE4.so"
#define CONFIG_NAME "pes21_nx.cfg"
#define LOG_NAME "debug.log"
#define APPSTATE_NAME "appstate.txt"

// DEBUG_LOG is supplied by `make DIAGNOSTICS=1`. Release builds leave it
// undefined, making debugPrintf a no-op and removing expensive GL readbacks.

// actual screen size
extern int screen_width;
extern int screen_height;

typedef struct {
  int screen_width;
  int screen_height;
  int trilinear_filter;
  int show_fps;
  int fuzzy_seek;
  int force_gles;
} Config;

extern Config config;

int read_config(const char *file);
int write_config(const char *file);

#endif
