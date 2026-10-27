#include "loading_popup.h"
#include <pthread.h>
#include <stdio.h>
#include <string.h>
static pthread_mutex_t loading_mutex=PTHREAD_MUTEX_INITIALIZER;
static NxLoadingView loading;
static uint64_t serial;
uint64_t nx_loading_begin(const char *title,const char *message) {
  pthread_mutex_lock(&loading_mutex);
  if(!++serial)++serial;
  loading.token=serial;
  snprintf(loading.title,sizeof(loading.title),"%s",title && *title ? title : "PLEASE WAIT");
  snprintf(loading.message,sizeof(loading.message),"%s",message && *message ? message : "Loading...");
  uint64_t token=serial;pthread_mutex_unlock(&loading_mutex);return token;
}
int nx_loading_update(uint64_t token,const char *message) {
  pthread_mutex_lock(&loading_mutex);int ok=token && token==loading.token;
  if(ok)snprintf(loading.message,sizeof(loading.message),"%s",message ? message : "Loading...");
  pthread_mutex_unlock(&loading_mutex);return ok;
}
int nx_loading_finish(uint64_t token) {
  pthread_mutex_lock(&loading_mutex);int ok=token && token==loading.token;
  if(ok)memset(&loading,0,sizeof(loading));
  pthread_mutex_unlock(&loading_mutex);return ok;
}
int nx_loading_active(void) {
  pthread_mutex_lock(&loading_mutex);int active=loading.token!=0;
  pthread_mutex_unlock(&loading_mutex);return active;
}
void nx_loading_snapshot(NxLoadingView *out) {
  if(!out)return;
  pthread_mutex_lock(&loading_mutex);*out=loading;pthread_mutex_unlock(&loading_mutex);
}
