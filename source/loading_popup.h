#ifndef PESNX_LOADING_POPUP_H
#define PESNX_LOADING_POPUP_H
#include <stdint.h>
typedef struct {uint64_t token;char title[64],message[160];} NxLoadingView;
/* A request owns its token until finish. Stale worker replies cannot close a
 * newer operation. There is no simulated connection or artificial delay. */
uint64_t nx_loading_begin(const char *title,const char *message);
int nx_loading_update(uint64_t token,const char *message);
int nx_loading_finish(uint64_t token);
int nx_loading_active(void);
void nx_loading_snapshot(NxLoadingView *out);
#endif
