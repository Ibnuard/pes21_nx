#define _POSIX_C_SOURCE 200809L
#include "manager_online_http.h"
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <zlib.h>
#if defined(__SWITCH__) || defined(MANAGER_ONLINE_HOST_CURL)
#include <curl/curl.h>
#endif
#ifdef __SWITCH__
#include <switch.h>
#endif

void mo_wipe(void *memory,size_t size){volatile unsigned char *p=memory;while(size--)*p++=0;}
int mo_random_key(char out[37]){
  unsigned char bytes[16];
#ifdef __SWITCH__
  randomGet(bytes,sizeof(bytes));
#else
  FILE *f=fopen("/dev/urandom","rb");if(!f)return 0;
  int ok=fread(bytes,1,sizeof(bytes),f)==sizeof(bytes);fclose(f);if(!ok)return 0;
#endif
  bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;
  snprintf(out,37,"%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
      bytes[0],bytes[1],bytes[2],bytes[3],bytes[4],bytes[5],bytes[6],bytes[7],
      bytes[8],bytes[9],bytes[10],bytes[11],bytes[12],bytes[13],bytes[14],bytes[15]);
  mo_wipe(bytes,sizeof(bytes));return 1;
}
void mo_http_free(MoHttpResponse *r){if(r->body){mo_wipe(r->body,r->size);free(r->body);}memset(r,0,sizeof(*r));}
#if defined(__SWITCH__) || defined(MANAGER_ONLINE_HOST_CURL)
static pthread_once_t curl_once=PTHREAD_ONCE_INIT;
static int curl_ready;
typedef struct {MoHttpResponse *response;size_t limit;} MoDownload;
static void curl_start(void){curl_ready=curl_global_init(CURL_GLOBAL_DEFAULT)==CURLE_OK;}
static size_t write_body(char *data,size_t width,size_t count,void *arg){
  MoDownload *download=arg;MoHttpResponse *r=download->response;if(width && count>SIZE_MAX/width)return 0;size_t n=width*count;
  if(n>download->limit-r->size)return 0;
  char *next=realloc(r->body,r->size+n+1);if(!next)return 0;
  r->body=next;memcpy(next+r->size,data,n);r->size+=n;next[r->size]=0;return n;
}
static int header_text(const char *s){return s && !strchr(s,'\r')&&!strchr(s,'\n');}
static int add_header(struct curl_slist **headers,const char *value){
  struct curl_slist *next=curl_slist_append(*headers,value);
  if(!next)return 0;
  *headers=next;return 1;
}
#endif
void mo_http_perform(const MoHttpRequest *q,MoHttpResponse *r){
  memset(r,0,sizeof(*r));r->transport_error=1;
#if defined(__SWITCH__) || defined(MANAGER_ONLINE_HOST_CURL)
  if(!q || q->path[0]!='/' || strstr(q->path,"://") || !header_text(q->path) ||
      !header_text(q->access)||!header_text(q->key)||q->environment>2)return;
  pthread_once(&curl_once,curl_start);if(!curl_ready)return;
  CURL *curl=curl_easy_init();if(!curl)return;
  const size_t limit=strstr(q->path,"/playback")?MO_RECORDING_LIMIT:MO_HTTP_LIMIT;
  MoDownload download={r,limit};
  char url[512],bearer[MO_TOKEN_SIZE+32],idempotency[64];
  snprintf(url,sizeof(url),"%s%s",MANAGER_ONLINE_BASE,q->path);
  struct curl_slist *headers=NULL;
  int headers_ok=add_header(&headers,"Accept: application/json, application/gzip")&&
      add_header(&headers,"Content-Type: application/json")&&
      add_header(&headers,"X-FNX-Online-Version: " MANAGER_ONLINE_VERSION)&&
      add_header(&headers,"X-FNX-Catalog-Hash: " MANAGER_ONLINE_CATALOG)&&
      add_header(&headers,"X-FNX-API-Schema: 1")&&
      add_header(&headers,"X-FNX-Client-Build: fnx-online-v122");
  if(q->environment)headers_ok=headers_ok&&add_header(&headers,q->environment==2?"X-FNX-Environment: TEST":"X-FNX-Environment: PRODUCTION");
  if(q->access[0]){snprintf(bearer,sizeof(bearer),"Authorization: Bearer %s",q->access);headers_ok=headers_ok&&add_header(&headers,bearer);}
  if(q->key[0]){snprintf(idempotency,sizeof(idempotency),"Idempotency-Key: %s",q->key);headers_ok=headers_ok&&add_header(&headers,idempotency);}
  if(!headers_ok){curl_slist_free_all(headers);curl_easy_cleanup(curl);mo_wipe(bearer,sizeof(bearer));return;}
  curl_easy_setopt(curl,CURLOPT_URL,url);
  curl_easy_setopt(curl,CURLOPT_PROTOCOLS,(long)CURLPROTO_HTTPS);
  curl_easy_setopt(curl,CURLOPT_FOLLOWLOCATION,0L);
  curl_easy_setopt(curl,CURLOPT_SSL_VERIFYPEER,1L);
  curl_easy_setopt(curl,CURLOPT_SSL_VERIFYHOST,2L);
  curl_easy_setopt(curl,CURLOPT_SSLVERSION,(long)CURL_SSLVERSION_TLSv1_2);
  curl_easy_setopt(curl,CURLOPT_CONNECTTIMEOUT_MS,6000L);
  curl_easy_setopt(curl,CURLOPT_TIMEOUT_MS,20000L);
  curl_easy_setopt(curl,CURLOPT_NOSIGNAL,1L);
  curl_easy_setopt(curl,CURLOPT_HTTPHEADER,headers);
  curl_easy_setopt(curl,CURLOPT_USERAGENT,"FootballNX-Switch/1.0.0");
  curl_easy_setopt(curl,CURLOPT_ACCEPT_ENCODING,"gzip");
  curl_easy_setopt(curl,CURLOPT_WRITEFUNCTION,write_body);
  curl_easy_setopt(curl,CURLOPT_WRITEDATA,&download);
  if(strcmp(q->method,"GET")){
    curl_easy_setopt(curl,CURLOPT_CUSTOMREQUEST,q->method);
    curl_easy_setopt(curl,CURLOPT_POSTFIELDS,q->body);
    curl_easy_setopt(curl,CURLOPT_POSTFIELDSIZE,(long)strlen(q->body));
  }
  CURLcode result=curl_easy_perform(curl);long status=0;
  curl_easy_getinfo(curl,CURLINFO_RESPONSE_CODE,&status);r->status=(int)status;r->transport_error=result!=CURLE_OK;
  curl_slist_free_all(headers);curl_easy_cleanup(curl);mo_wipe(bearer,sizeof(bearer));
  if(!r->transport_error && r->size>=2 && (unsigned char)r->body[0]==31 && (unsigned char)r->body[1]==139){
    char *decoded=malloc(limit+1);z_stream z={0};
    if(!decoded){r->transport_error=1;return;}
    z.next_in=(Bytef *)r->body;z.avail_in=(uInt)r->size;z.next_out=(Bytef *)decoded;z.avail_out=(uInt)limit;
    int started=inflateInit2(&z,15+32)==Z_OK;
    int ok=started && inflate(&z,Z_FINISH)==Z_STREAM_END && z.avail_in==0;
    size_t n=z.total_out;if(started)inflateEnd(&z);
    if(ok){mo_wipe(r->body,r->size);free(r->body);r->body=decoded;r->size=n;decoded[n]=0;}
    else {mo_wipe(decoded,limit+1);free(decoded);r->transport_error=1;}
  }
#else
  (void)q;
#endif
}
