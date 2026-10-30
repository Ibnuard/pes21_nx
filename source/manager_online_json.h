#ifndef PESNX_MANAGER_ONLINE_JSON_H
#define PESNX_MANAGER_ONLINE_JSON_H
#include <stddef.h>
#include <stdint.h>
/* Bounded JSON reader for untrusted API bodies; no pointers into mutable saves. */
typedef struct { int start,end,next,count;unsigned char type; } MjToken;
typedef struct {const char *text;size_t bytes;MjToken *tokens;int count,capacity;} MjDoc;
enum {MJ_OBJECT=1,MJ_ARRAY,MJ_STRING,MJ_NUMBER,MJ_TRUE,MJ_FALSE,MJ_NULL};
int mj_parse(MjDoc *doc,const char *text,size_t bytes,MjToken *tokens,int capacity);
int mj_get(const MjDoc *doc,int object,const char *key);
int mj_at(const MjDoc *doc,int array,int index);
int mj_text(const MjDoc *doc,int token,char *out,size_t capacity);
int mj_u64(const MjDoc *doc,int token,uint64_t *out);
int mj_bool(const MjDoc *doc,int token,int *out);
int mj_is(const MjDoc *doc,int token,int type);
int mj_copy(const MjDoc *doc,int token,char *out,size_t capacity);
int mj_quote(const char *text,char *out,size_t capacity);
#endif
