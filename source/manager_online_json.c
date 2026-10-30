#include "manager_online_json.h"
#include <limits.h>
#include <string.h>

typedef struct {MjDoc *doc;size_t pos;} Reader;
static void ws(Reader *r){while(r->pos<r->doc->bytes && strchr(" \r\n\t",r->doc->text[r->pos]))r->pos++;}
static int hex(char c){return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:c>='A'&&c<='F'?c-'A'+10:-1;}
static int value(Reader *r,int depth){
  MjDoc *d=r->doc;ws(r);
  if(depth>32 || r->pos>=d->bytes || d->count>=d->capacity)return -1;
  const int id=d->count++;MjToken *t=&d->tokens[id];memset(t,0,sizeof(*t));t->start=(int)r->pos;
  char c=d->text[r->pos++];
  if(c=='{' || c=='['){
    t->type=c=='{'?MJ_OBJECT:MJ_ARRAY;char close=c=='{'?'}':']';ws(r);
    if(r->pos<d->bytes && d->text[r->pos]==close)r->pos++;
    else for(;;){
      if(c=='{'){
        ws(r);if(r->pos>=d->bytes || d->text[r->pos]!='"' || value(r,depth+1)<0)return -1;
        ws(r);if(r->pos>=d->bytes || d->text[r->pos++]!=':')return -1;
      }
      if(value(r,depth+1)<0)return -1;
      t->count++;ws(r);if(r->pos>=d->bytes)return -1;
      char sep=d->text[r->pos++];if(sep==close)break;if(sep!=',')return -1;
    }
  }else if(c=='"'){
    t->type=MJ_STRING;int closed=0;
    while(r->pos<d->bytes){
      unsigned char x=(unsigned char)d->text[r->pos++];
      if(x=='"'){closed=1;break;}if(x<32)return -1;
      if(x=='\\'){
        if(r->pos>=d->bytes)return -1;
        char e=d->text[r->pos++];
        if(e=='u'){for(int i=0;i<4;i++)if(r->pos>=d->bytes || hex(d->text[r->pos++])<0)return -1;}
        else if(!strchr("\"\\/bfnrt",e))return -1;
      }
    }
    if(!closed)return -1;
  }else if(c=='t' || c=='f' || c=='n'){
    const char *word=c=='t'?"true":c=='f'?"false":"null";size_t n=strlen(word);
    if(t->start+(int)n>(int)d->bytes || memcmp(d->text+t->start,word,n))return -1;
    r->pos=t->start+n;t->type=c=='t'?MJ_TRUE:c=='f'?MJ_FALSE:MJ_NULL;
  }else{
    t->type=MJ_NUMBER;r->pos--;
    if(d->text[r->pos]=='-')r->pos++;
    if(r->pos>=d->bytes)return -1;
    if(d->text[r->pos]=='0')r->pos++;
    else {if(d->text[r->pos]<'1'||d->text[r->pos]>'9')return -1;while(r->pos<d->bytes && d->text[r->pos]>='0'&&d->text[r->pos]<='9')r->pos++;}
    if(r->pos<d->bytes && d->text[r->pos]=='.'){
      r->pos++;size_t begin=r->pos;while(r->pos<d->bytes && d->text[r->pos]>='0'&&d->text[r->pos]<='9')r->pos++;if(r->pos==begin)return -1;
    }
    if(r->pos<d->bytes && (d->text[r->pos]=='e'||d->text[r->pos]=='E')){
      r->pos++;if(r->pos<d->bytes && (d->text[r->pos]=='+'||d->text[r->pos]=='-'))r->pos++;
      size_t begin=r->pos;while(r->pos<d->bytes && d->text[r->pos]>='0'&&d->text[r->pos]<='9')r->pos++;if(r->pos==begin)return -1;
    }
  }
  t->end=(int)r->pos;t->next=d->count;return id;
}
int mj_parse(MjDoc *d,const char *text,size_t bytes,MjToken *tokens,int capacity){
  if(!d||!text||!tokens||capacity<1||bytes>INT_MAX||memchr(text,0,bytes))return 0;
  *d=(MjDoc){text,bytes,tokens,0,capacity};Reader r={d,0};
  if(value(&r,0)!=0)return 0;
  ws(&r);return r.pos==bytes;
}
int mj_is(const MjDoc *d,int t,int type){return d && t>=0 && t<d->count && d->tokens[t].type==type;}
int mj_at(const MjDoc *d,int array,int index){
  if(!mj_is(d,array,MJ_ARRAY)||index<0||index>=d->tokens[array].count)return -1;
  int t=array+1;while(index--)t=d->tokens[t].next;return t;
}
static int put_utf8(unsigned code,char *out,size_t cap,size_t *used){
  char b[4];size_t n;
  if(!code || code>0x10ffff || (code>=0xd800&&code<=0xdfff))return 0;
  if(code<0x80){b[0]=(char)code;n=1;}
  else if(code<0x800){b[0]=0xc0|(code>>6);b[1]=0x80|(code&63);n=2;}
  else if(code<0x10000){b[0]=0xe0|(code>>12);b[1]=0x80|((code>>6)&63);b[2]=0x80|(code&63);n=3;}
  else {b[0]=0xf0|(code>>18);b[1]=0x80|((code>>12)&63);b[2]=0x80|((code>>6)&63);b[3]=0x80|(code&63);n=4;}
  if(*used+n>=cap)return 0;
  memcpy(out+*used,b,n);*used+=n;return 1;
}
int mj_text(const MjDoc *d,int token,char *out,size_t cap){
  if(!out||!cap)return 0;
  out[0]=0;
  if(!mj_is(d,token,MJ_STRING))return 0;
  const char *s=d->text;int p=d->tokens[token].start+1,end=d->tokens[token].end-1;size_t n=0;
  while(p<end){
    unsigned c=(unsigned char)s[p++];
    if(c=='\\'){
      char e=s[p++];
      if(e=='u'){
        c=0;for(int i=0;i<4;i++)c=(c<<4)|(unsigned)hex(s[p++]);
        if(c>=0xd800&&c<=0xdbff){
          if(p+6>end||s[p]!='\\'||s[p+1]!='u')goto bad;
          p+=2;unsigned lo=0;for(int i=0;i<4;i++)lo=(lo<<4)|(unsigned)hex(s[p++]);
          if(lo<0xdc00||lo>0xdfff)goto bad;
          c=0x10000+((c-0xd800)<<10)+(lo-0xdc00);
        }
      }else c=e=='b'?'\b':e=='f'?'\f':e=='n'?'\n':e=='r'?'\r':e=='t'?'\t':(unsigned char)e;
    }else if(c>=0x80){
      unsigned need=c>=0xc2&&c<=0xdf?1:c>=0xe0&&c<=0xef?2:c>=0xf0&&c<=0xf4?3:0;
      if(!need||p+(int)need>end)goto bad;
      unsigned min=need==1?0x80:need==2?0x800:0x10000;
      c&=(1u<<(6-need))-1u;
      while(need--){unsigned b=(unsigned char)s[p++];if((b&0xc0)!=0x80)goto bad;c=(c<<6)|(b&63);}
      if(c<min)goto bad;
    }
    if(!put_utf8(c,out,cap,&n))goto bad;
  }
  out[n]=0;return 1;
bad:out[0]=0;return 0;
}
int mj_get(const MjDoc *d,int object,const char *key){
  if(!mj_is(d,object,MJ_OBJECT)||!key)return -1;
  int result=-1,t=object+1;
  for(int i=0;i<d->tokens[object].count;i++){
    char name[96];if(!mj_text(d,t,name,sizeof(name)))return -1;
    int v=t+1;if(!strcmp(name,key)){if(result>=0)return -1;result=v;}t=d->tokens[v].next;
  }
  return result;
}
int mj_u64(const MjDoc *d,int token,uint64_t *out){
  if(!d||!out||token<0||token>=d->count)return 0;
  MjToken t=d->tokens[token];if(t.type!=MJ_NUMBER&&t.type!=MJ_STRING)return 0;
  int p=t.start+(t.type==MJ_STRING),end=t.end-(t.type==MJ_STRING);if(p==end)return 0;uint64_t n=0;
  for(;p<end;p++){unsigned c=(unsigned char)d->text[p];if(c<'0'||c>'9'||n>(UINT64_MAX-(c-'0'))/10)return 0;n=n*10+c-'0';}
  *out=n;return 1;
}
int mj_bool(const MjDoc *d,int token,int *out){
  if(!out)return 0;
  if(mj_is(d,token,MJ_TRUE)){*out=1;return 1;}
  if(mj_is(d,token,MJ_FALSE)){*out=0;return 1;}return 0;
}
int mj_copy(const MjDoc *d,int token,char *out,size_t cap){
  if(!d||token<0||token>=d->count||!out||!cap)return 0;
  MjToken t=d->tokens[token];size_t n=(size_t)(t.end-t.start);
  if(n>=cap){out[0]=0;return 0;}memcpy(out,d->text+t.start,n);out[n]=0;return 1;
}
int mj_quote(const char *text,char *out,size_t cap){
  static const char h[]="0123456789abcdef";if(!text||!out||cap<3)return 0;size_t n=0;out[n++]='"';
  for(const unsigned char *p=(const unsigned char *)text;*p;p++){
    size_t need=*p<32?6:(*p=='"'||*p=='\\')?2:1;if(n+need+2>cap){out[0]=0;return 0;}
    if(*p<32){out[n++]='\\';out[n++]='u';out[n++]='0';out[n++]='0';out[n++]=h[*p>>4];out[n++]=h[*p&15];}
    else {if(need==2)out[n++]='\\';out[n++]=(char)*p;}
  }
  out[n++]='"';out[n]=0;return 1;
}
