#pragma once
#include <stddef.h>

/* Optional two-pack canary. A present but invalid manifest is an error. */
int pes_loose_cpk_init(const char *build_id,
                      int (*hash_file)(const char *, unsigned char[32]),
                      char *error, size_t error_size);
/* Returned paths have static lifetime (CRI binding can be asynchronous). */
const char *pes_loose_cpk_path(const char *native_path);
