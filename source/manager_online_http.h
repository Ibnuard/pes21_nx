#ifndef PESNX_MANAGER_ONLINE_HTTP_H
#define PESNX_MANAGER_ONLINE_HTTP_H
#include <stddef.h>
#include <stdint.h>
#define MANAGER_ONLINE_BASE "https://wedreamku.my.id/footballnx/api/v1"
#define MANAGER_ONLINE_VERSION "1.0.0"
#define MANAGER_ONLINE_CATALOG "2ffab2858daa681400e89445d75c28c0d8ac951bd36b0ec4af35ff08020f1222"
#define MANAGER_ONLINE_PAIR "e861c583ec78e9ae"
enum {MO_HTTP_LIMIT=524288,MO_RECORDING_LIMIT=4194304,MO_TOKEN_SIZE=513};
typedef struct {
  char method[8],path[192],body[12288],access[MO_TOKEN_SIZE],key[37];
  /* Assertion only: the server derives the realm from the authenticated account. */
  uint32_t environment; /* 0=authentication/discovery, 1=PRODUCTION, 2=TEST */
} MoHttpRequest;
typedef struct {int status,transport_error;char *body;size_t size;} MoHttpResponse;
/* One bounded worker owns a request. Never run this on the render/game thread. */
void mo_http_perform(const MoHttpRequest *request,MoHttpResponse *response);
void mo_http_free(MoHttpResponse *response);
void mo_wipe(void *memory,size_t bytes);
int mo_random_key(char out[37]);
#endif
