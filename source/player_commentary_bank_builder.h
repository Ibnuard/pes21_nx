#ifndef PESNX_PLAYER_COMMENTARY_BANK_BUILDER_H
#define PESNX_PLAYER_COMMENTARY_BANK_BUILDER_H
#include "player_commentary_types.h"
#include <stdlib.h>
#include <string.h>

/* Bounded UTF reconstruction. The package pins the complete accepted bank;
 * parsed offsets are still checked before any pointer arithmetic. */
typedef struct { const unsigned char *p; uint32_t n, rows, row, strings, blobs;
  uint16_t stride, count; struct { const char *name; uint8_t mode,kind,width;
    uint32_t at, name_at; } f[128]; } PcUtf;
typedef struct { unsigned char *p; size_t n, capacity; } PcBytes;
static inline uint32_t pc_be(const unsigned char *p,unsigned n) {
  uint32_t v=0; while(n--) v=(v<<8)|*p++; return v;
}
static inline void pc_put(unsigned char *p,uint64_t v,unsigned n) {
  while(n) { p[--n]=(unsigned char)v; v>>=8; }
}
static inline uint32_t pc_le(const unsigned char *p,unsigned n) {
  uint32_t v=0; while(n) { v=(v<<8)|p[--n]; } return v;
}
static inline void pc_lput(unsigned char *p,uint32_t v,unsigned n) {
  while(n--) { *p++=(unsigned char)v; v>>=8; }
}
static inline uint64_t pc_fnv(const void *p,size_t n) {
  const unsigned char *b=p; uint64_t h=UINT64_C(0xcbf29ce484222325);
  while(n--) h=(h^*b++)*UINT64_C(0x100000001b3);
  return h;
}
static inline int pc_range(size_t n,size_t at,size_t bytes) {
  return at<=n && bytes<=n-at;
}
static inline const char *pc_string(const PcUtf *u,uint32_t at) {
  if(at>=u->blobs-u->strings) return NULL;
  const char *s=(const char *)u->p+u->strings+at;
  return memchr(s,0,u->blobs-u->strings-at)?s:NULL;
}
static inline int pc_utf(PcUtf *u,const void *p,size_t n) {
  static const unsigned char widths[12]={1,1,2,2,4,4,8,8,4,0,4,8};
  memset(u,0,sizeof(*u)); if(!p || n<32 || n>PC_BANK_MAX_BYTES) return 0;
  const unsigned char *b=p; if(memcmp(b,"@UTF",4)) return 0;
  u->p=b; u->n=pc_be(b+4,4)+8u; if(u->n<32 || u->n>n) return 0;
  u->row=pc_be(b+10,2)+8u; u->strings=pc_be(b+12,4)+8u;
  u->blobs=pc_be(b+16,4)+8u; u->count=pc_be(b+24,2);
  u->stride=pc_be(b+26,2); u->rows=pc_be(b+28,4);
  if(!u->count || u->count>128 || !u->rows || u->rows>65535 ||
     u->row<32 || u->row>u->strings || u->strings>u->blobs ||
     u->blobs>u->n || !pc_range(u->strings,u->row,(size_t)u->stride*u->rows)) return 0;
  uint32_t pos=32,relative=0;
  for(unsigned i=0;i<u->count;i++) {
    if(!pc_range(u->row,pos,5)) return 0;
    unsigned flag=b[pos],kind=flag&15,mode=flag&240;
    if(kind>=12 || !widths[kind] || (mode!=16 && mode!=48 && mode!=80)) return 0;
    u->f[i].kind=kind; u->f[i].mode=mode; u->f[i].width=widths[kind];
    u->f[i].name_at=pc_be(b+pos+1,4); u->f[i].name=pc_string(u,u->f[i].name_at);
    if(!u->f[i].name) return 0;
    pos+=5;
    if(mode==48) { u->f[i].at=pos; if(!pc_range(u->row,pos,widths[kind])) return 0; pos+=widths[kind]; }
    else if(mode==80) { u->f[i].at=relative; relative+=widths[kind]; }
  }
  return pos==u->row && relative==u->stride;
}
static inline int pc_field(const PcUtf *u,const char *name) {
  for(unsigned i=0;i<u->count;i++) if(!strcmp(u->f[i].name,name)) return (int)i;
  return -1;
}
static inline const unsigned char *pc_cell(const PcUtf *u,uint32_t row,unsigned f) {
  static const unsigned char zero[8]={0};
  if(row>=u->rows || f>=u->count) return NULL;
  return u->f[f].mode==16?zero:u->p+u->f[f].at+(u->f[f].mode==80?u->row+(size_t)row*u->stride:0);
}
static inline uint64_t pc_num(const PcUtf *u,uint32_t row,int f) {
  if(f<0) return UINT64_MAX;
  const unsigned char *p=pc_cell(u,row,(unsigned)f);
  uint64_t v=0; for(unsigned i=0;i<u->f[f].width;i++) v=(v<<8)|p[i]; return v;
}
static inline int pc_blob(const PcUtf *u,uint32_t row,int f,const unsigned char **p,uint32_t *n) {
  if(f<0 || u->f[f].kind!=11) return 0;
  const unsigned char *c=pc_cell(u,row,(unsigned)f);
  uint32_t at=pc_be(c,4),sz=pc_be(c+4,4);
  if(!pc_range(u->n-u->blobs,at,sz)) return 0;
  *p=u->p+u->blobs+at; *n=sz; return 1;
}
static inline const char *pc_text(const PcUtf *u,uint32_t row,int f) {
  return f>=0 && u->f[f].kind==10?pc_string(u,(uint32_t)pc_num(u,row,f)):NULL;
}
static inline int pc_child(const PcUtf *u,const char *name,PcUtf *out) {
  const unsigned char *p; uint32_t n;
  return pc_blob(u,0,pc_field(u,name),&p,&n) && pc_utf(out,p,n) && out->n==n;
}
static inline const PcBankOwner *pc_bank_owner(const PcBankCatalog *cat,uint32_t id) {
  uint32_t a=0,b=cat->owner_count;
  while(a<b) { uint32_t m=a+(b-a)/2; if(cat->owners[m].native_id<id) a=m+1; else b=m; }
  return a<cat->owner_count && cat->owners[a].native_id==id?cat->owners+a:NULL;
}
static inline int pc_owned_name(const PcBankOwner *owner,const PcBankCue *cue) {
  if(!owner->fingerprint || strlen(owner->fingerprint)!=20 ||
     !owner->row_sha256 || strlen(owner->row_sha256)!=64 || !cue->name ||
     strlen(cue->name)!=16 || strncmp(cue->name,cue->type==0?"EN_A1_P0_R":"EN_B1_P0_R",10)) return 0;
  uint32_t id=0;
  for(unsigned i=10;i<16;i++) {
    if(cue->name[i]<'0' || cue->name[i]>'9')return 0;
    id=id*10u+(uint32_t)(cue->name[i]-'0');
  }
  return id==owner->native_id;
}
static inline void pc_bank_free(PcBankResult *r) {
  if(r) { free(r->data); memset(r,0,sizeof(*r)); }
}
typedef struct { const PcBankCue *cue; uint16_t index; uint32_t blob, name; } PcChange;
static inline int pc_changed(PcChange *c,unsigned n,uint32_t row) {
  for(unsigned i=0;i<n;i++) if(c[i].index==row) return (int)i;
  return -1;
}
/* These names are project code, not payload metadata. Unknown fields retain
 * their complete original encoded values, including binary graph edges. */
static inline int pc_value(unsigned table,const char *field,const PcBankCue *c,uint32_t index,
                           uint64_t *v) {
  if(table==0) {
    if(!strcmp(field,"CueId") || !strcmp(field,"ReferenceIndex")) *v=index;
    else if(!strcmp(field,"Length")) *v=c->duration_ms;
    else return 0;
  } else if(table==1) { if(strcmp(field,"CueIndex")) return 0; *v=index; }
  else if(table==2) {
    if(!strcmp(field,"Id")) *v=index;
    else if(!strcmp(field,"Streaming")) *v=0;
    else if(!strcmp(field,"EncodeType")) *v=c->encode_type;
    else if(!strcmp(field,"NumChannels")) *v=c->channels;
    else if(!strcmp(field,"LoopFlag")) *v=c->loop_flag;
    else if(!strcmp(field,"SamplingRate")) *v=c->rate;
    else if(!strcmp(field,"NumSamples")) *v=c->samples;
    else return 0;
  } else if(table==5 && !strcmp(field,"EventIndex")) *v=index;
  else return 0;
  return 1;
}
static inline const char *pc_graph_field(unsigned table) {
  return table==3?"ReferenceItems":table==4?"Command":table==6?"TrackIndex":"";
}
static inline unsigned pc_graph_bytes(unsigned table) { return table==3?4:table==4?10:table==6?2:0; }
static inline int pc_rebuild_child(const PcUtf *u,unsigned table,PcChange *changes,unsigned nc,
                                  uint32_t rows,PcBytes *out) {
  uint8_t mode[128]; uint32_t rowoff[128]; size_t desc=0,stride=0;
  size_t strsize=u->blobs-u->strings,blobsize=u->n-u->blobs;
  const unsigned graphbytes=pc_graph_bytes(table);
  if(table==1) for(unsigned j=0;j<nc;j++) if(changes[j].index>=u->rows) {
    changes[j].name=(uint32_t)strsize; strsize+=strlen(changes[j].cue->name)+1;
  }
  if(graphbytes) for(unsigned j=0;j<nc;j++) if(changes[j].index>=u->rows) {
    blobsize=(blobsize+3)&~(size_t)3; changes[j].blob=(uint32_t)blobsize; blobsize+=graphbytes;
  }
  for(unsigned f=0;f<u->count;f++) {
    mode[f]=u->f[f].mode;
    if(mode[f]!=80) for(unsigned j=0;j<nc;j++) {
      uint64_t value;
      if((pc_value(table,u->f[f].name,changes[j].cue,changes[j].index,&value) &&
          value!=pc_num(u,0,(int)f)) ||
         (table==1 && changes[j].index>=u->rows && !strcmp(u->f[f].name,"CueName")) ||
         (graphbytes && changes[j].index>=u->rows && !strcmp(u->f[f].name,pc_graph_field(table)))) {
        mode[f]=80;break;
      }
    }
    desc+=5+(mode[f]==48?u->f[f].width:0); rowoff[f]=(uint32_t)stride;
    if(mode[f]==80) stride+=u->f[f].width;
  }
  size_t rowstart=32+desc,strstart=rowstart+stride*rows,blobstart=(strstart+strsize+3)&~(size_t)3;
  size_t total=blobstart+blobsize;
  if(stride>65535 || rowstart>65543 || total>PC_BANK_MAX_BYTES) return 0;
  unsigned char *p=calloc(1,total); if(!p) return 0;
  memcpy(p,u->p,32); pc_put(p+4,total-8,4); pc_put(p+10,rowstart-8,2);
  pc_put(p+12,strstart-8,4); pc_put(p+16,blobstart-8,4); pc_put(p+26,stride,2);pc_put(p+28,rows,4);
  size_t d=32;
  for(unsigned f=0;f<u->count;f++) { p[d]=mode[f]|u->f[f].kind; pc_put(p+d+1,u->f[f].name_at,4);d+=5;
    if(mode[f]==48) { memcpy(p+d,pc_cell(u,0,f),u->f[f].width);d+=u->f[f].width; }
  }
  memcpy(p+strstart,u->p+u->strings,u->blobs-u->strings);
  memcpy(p+blobstart,u->p+u->blobs,u->n-u->blobs);
  for(unsigned j=0;j<nc;j++) if(changes[j].index>=u->rows) {
    if(table==1) strcpy((char *)p+strstart+changes[j].name,changes[j].cue->name);
    else if(graphbytes) { unsigned char *q=p+blobstart+changes[j].blob; uint32_t index=changes[j].index;
      if(table==3) { pc_put(q,1,2);pc_put(q+2,index,2); }
      else if(table==4) { pc_put(q,2000,2); q[2]=4;pc_put(q+3,2,2);pc_put(q+5,index,2); }
      else pc_put(q,index,2);
    }
  }
  /* CueName is emitted in strict lexical order, keeping every old mapping. */
  uint32_t original=0,appended=0;
  for(uint32_t row=0;row<rows;row++) {
    uint32_t oldrow=row<u->rows?row:0; int ci=table==1?-1:pc_changed(changes,nc,row);
    if(table==1) {
      while(appended<nc && changes[appended].index<u->rows) appended++;
      const char *old=original<u->rows?pc_text(u,original,pc_field(u,"CueName")):NULL;
      const char *add=appended<nc?changes[appended].cue->name:NULL;
      if(add && (!old || strcmp(add,old)<0)) { ci=(int)appended++;oldrow=0; }
      else { if(!old) { free(p);return 0; } oldrow=original++; }
    }
    for(unsigned f=0;f<u->count;f++) if(mode[f]==80) {
      unsigned width=u->f[f].width; unsigned char *q=p+rowstart+(size_t)row*stride+rowoff[f];
      memcpy(q,pc_cell(u,oldrow,f),width);
      if(ci>=0) {
        uint64_t v; PcChange *ch=changes+ci;
        if(pc_value(table,u->f[f].name,ch->cue,ch->index,&v)) {
          if(width<8 && v>(((uint64_t)1<<(width*8))-1)) { free(p);return 0; } pc_put(q,v,width);
        } else if(table==1 && !strcmp(u->f[f].name,"CueName")) pc_put(q,ch->name,4);
        else if(graphbytes && ch->index>=u->rows && !strcmp(u->f[f].name,pc_graph_field(table))) {
          pc_put(q,ch->blob,4);pc_put(q+4,graphbytes,4);
        }
      }
    }
  }
  PcUtf check; if(!pc_utf(&check,p,total)) { free(p);return 0; }
  out->p=p;out->n=total;out->capacity=total;return 1;
}
/* Repack top binary children once, preserving every unmodified top field. */
static inline int pc_rebuild_top(const PcUtf *u,const char **names,PcBytes *children,PcBytes *out) {
  size_t start=u->blobs,total=start;
  for(unsigned f=0;f<u->count;f++) if(u->f[f].kind==11) {
    const unsigned char *p;uint32_t n;if(!pc_blob(u,0,f,&p,&n))return 0;
    for(unsigned j=0;j<8;j++) if(!strcmp(u->f[f].name,names[j])) { n=(uint32_t)children[j].n;break; }
    total=(total+3)&~(size_t)3;total+=n;
  }
  if(total>PC_BANK_MAX_BYTES-48u) return 0;
  unsigned char *p=calloc(1,total);if(!p)return 0;
  memcpy(p,u->p,start);pc_put(p+4,total-8,4);size_t cursor=start;
  for(unsigned f=0;f<u->count;f++) if(u->f[f].kind==11) {
    const unsigned char *src=NULL;uint32_t n=0;
    if(!pc_blob(u,0,f,&src,&n)){free(p);return 0;}
    for(unsigned j=0;j<8;j++) if(!strcmp(u->f[f].name,names[j])) {src=children[j].p;n=(uint32_t)children[j].n;break;}
    if(u->f[f].mode==16 && n) {free(p);return 0;}
    cursor=(cursor+3)&~(size_t)3;
    if(u->f[f].mode!=16) {
      unsigned char *cell=p+(pc_cell(u,0,f)-u->p);
      pc_put(cell,cursor-start,4);pc_put(cell+4,n,4);
    }
    if(n)memcpy(p+cursor,src,n);
    cursor+=n;
  }
  PcUtf check;if(!pc_utf(&check,p,total)){free(p);return 0;}
  out->p=p;out->n=total;out->capacity=total;return 1;
}
static inline int pc_awb(const PcUtf *top,PcChange *ch,unsigned count,PcBankRead reader,void *ctx,
                         PcBytes *out,PcBankResult *result,size_t retained) {
  const unsigned char *old;uint32_t oldn;
  if(!pc_blob(top,0,pc_field(top,"AwbFile"),&old,&oldn) || oldn<20 || memcmp(old,"AFS2",4) ||
      old[5]!=4 || old[6]!=2 || pc_le(old+12,2)!=32 || pc_le(old+14,2)) return 0;
  uint32_t oldcount=pc_le(old+8,4); if(oldcount>65535 || !pc_range(oldn,16,(size_t)oldcount*6+4)) return 0;
  uint32_t n=oldcount+count;if(n>65535)return 0;
  /* Exact capacity bound includes one maximum selected recording at a time. */
  size_t capacity=16+(size_t)n*6+4;
  for(unsigned i=0;i<oldcount;i++) {
    uint32_t a=pc_le(old+16+oldcount*2+i*4,4),b=pc_le(old+16+oldcount*2+(i+1)*4,4);
    a=(a+31)&~31u;if(a>b || !pc_range(oldn,a,b-a))return 0;capacity+=31+b-a;
  }
  size_t largest=0;
  for(unsigned i=0;i<count;i++) {
    capacity+=31+ch[i].cue->bytes;
    if(ch[i].cue->bytes>largest)largest=ch[i].cue->bytes;
  }
  if(capacity>PC_BANK_MAX_BYTES || retained+capacity+largest>PC_BANK_MAX_SCRATCH)return 0;
  unsigned char *p=calloc(1,capacity);if(!p)return 0;
  memcpy(p,"AFS2",4);p[4]=2;p[5]=4;p[6]=2;pc_lput(p+8,n,4);pc_lput(p+12,32,2);
  size_t cursor=16+(size_t)n*6+4;unsigned oldi=0,newi=0;
  for(unsigned i=0;i<n;i++) {
    uint32_t oldid=oldi<oldcount?pc_le(old+16+oldi*2,2):65536;
    uint32_t newid=newi<count?ch[newi].index:65536;
    if(oldid==newid){free(p);return 0;}
    uint32_t id=oldid<newid?oldid:newid;pc_lput(p+16+i*2,id,2);pc_lput(p+16+n*2+i*4,(uint32_t)cursor,4);
    cursor=(cursor+31)&~(size_t)31;
    if(oldid<newid) {
      uint32_t a=pc_le(old+16+oldcount*2+oldi*4,4),b=pc_le(old+16+oldcount*2+(oldi+1)*4,4);
      a=(a+31)&~31u;memcpy(p+cursor,old+a,b-a);cursor+=b-a;oldi++;
    } else {
      const PcBankCue *cue=ch[newi++].cue;size_t got=0;
      unsigned char *audio=reader(ctx,cue->asset,PC_BANK_MAX_AUDIO,&got);
      if(!audio || got!=cue->bytes || got<96 || got>PC_BANK_MAX_AUDIO ||
         pc_fnv(audio,got)!=cue->payload_fnv || pc_fnv(audio,96)!=cue->header_fnv ||
         memcmp(audio,"HCA\0",4)) {free(audio);free(p);return 0;}
      int cipher=0;for(unsigned k=0;k+6<=96;k++) if(!memcmp(audio+k,"ciph\0\0",6))cipher=1;
      if(!cipher){free(audio);free(p);return 0;}
      memcpy(p+cursor,audio,got);cursor+=got;free(audio);
      size_t peak=retained+capacity+got;if(peak>result->scratch_peak)result->scratch_peak=peak;
    }
  }
  pc_lput(p+16+n*2+n*4,(uint32_t)cursor,4);out->p=p;out->n=cursor;out->capacity=capacity;return 1;
}
static inline int pc_bank_build(const void *base,size_t bytes,const PcBankCatalog *cat,
  const uint32_t *ids,size_t id_count,PcBankRead reader,void *ctx,PcBankResult *result) {
  static const char *names[8]={"CueTable","CueNameTable","WaveformTable","SynthTable","CommandTable","TrackTable","SequenceTable","AwbFile"};
  PcUtf top,tables[7];PcBytes children[8]={{0}},final={0};PcChange changes[PC_BANK_MAX_CUES];
  unsigned count=0;int ok=0;size_t allocated=0;
  if(!result)return 0;
  memset(result,0,sizeof(*result));
  if(!base || !cat || !reader || !ids || !id_count || id_count>PC_BANK_MAX_PLAYERS ||
    (cat->owner_count && !cat->owners) || (cat->cue_count && !cat->cues) ||
    (cat->baseline_header_count && !cat->baseline_headers) ||
    bytes!=cat->base_bytes || bytes>PC_BANK_MAX_BYTES || pc_fnv(base,bytes)!=cat->base_fnv ||
    cat->baseline_header_count>PC_BANK_MAX_HEADERS || !pc_utf(&top,base,bytes) ||
    strcmp(pc_text(&top,0,pc_field(&top,"Name"))?pc_text(&top,0,pc_field(&top,"Name")):"","10_PLAYER"))goto done;
  for(unsigned i=0;i<7;i++)if(!pc_child(&top,names[i],tables+i))goto done;
  uint32_t original=tables[0].rows,rows=original;
  for(unsigned i=1;i<7;i++)if(tables[i].rows!=original)goto done;
  if(original>=65535)goto done;
  memcpy(result->headers,cat->baseline_headers,cat->baseline_header_count*sizeof(uint64_t));
  result->header_count=cat->baseline_header_count;
  for(size_t i=0;i<id_count;i++) {
    int duplicate=0;for(size_t j=0;j<i;j++)if(ids[j]==ids[i])duplicate=1;if(duplicate)continue;
    const PcBankOwner *owner=pc_bank_owner(cat,ids[i]);if(!owner)continue;
    result->players[result->player_count++]=owner;
    if(owner->status!=PC_OWNER_NEW)continue;
    if(owner->cue_count>2 || !owner->cue_count || owner->cue_first>cat->cue_count || owner->cue_count>cat->cue_count-owner->cue_first)goto done;
    for(unsigned k=0;k<owner->cue_count;k++) {
      const PcBankCue *cue=cat->cues+owner->cue_first+k;
      if(count>=PC_BANK_MAX_CUES || cue->owner_index!=(uint32_t)(owner-cat->owners) ||
          (cue->type!=0 && cue->type!=24) || !cue->name || !cue->asset ||
          !cue->bytes || cue->bytes>PC_BANK_MAX_AUDIO || !pc_owned_name(owner,cue))goto done;
      changes[count++]=(PcChange){cue,0,0,0};
    }
  }
  /* Canonical lexical order independent of home/away publication order. */
  for(unsigned i=1;i<count;i++){PcChange v=changes[i];unsigned j=i;while(j && strcmp(changes[j-1].cue->name,v.cue->name)>0){changes[j]=changes[j-1];j--;}changes[j]=v;}
  for(unsigned i=0;i<count;i++) {
    if(i && !strcmp(changes[i-1].cue->name,changes[i].cue->name))goto done;
    uint32_t lo=0,hi=original;int found=0;
    while(lo<hi){uint32_t m=lo+(hi-lo)/2;const char *s=pc_text(tables+1,m,pc_field(tables+1,"CueName"));if(!s)goto done;
      int c=strcmp(s,changes[i].cue->name);if(c<0)lo=m+1;else hi=m;}
    if(lo<original){const char *s=pc_text(tables+1,lo,pc_field(tables+1,"CueName"));if(s && !strcmp(s,changes[i].cue->name)){changes[i].index=(uint16_t)pc_num(tables+1,lo,pc_field(tables+1,"CueIndex"));found=1;}}
    if(!found){if(rows>=65535)goto done;changes[i].index=(uint16_t)rows++;}
    if(changes[i].index>=rows)goto done;
    result->cues[i]=changes[i].cue;result->cue_indices[i]=changes[i].index;
    uint64_t h=changes[i].cue->header_fnv;unsigned j=0;for(;j<result->header_count;j++)if(result->headers[j]==h)break;
    if(j==result->header_count){if(j>=PC_BANK_MAX_HEADERS)goto done;result->headers[result->header_count++]=h;}
  }
  for(unsigned i=0;i<7;i++) {
    if(!pc_rebuild_child(tables+i,i,changes,count,rows,children+i))goto done;
    allocated+=children[i].n;if(allocated>PC_BANK_MAX_SCRATCH)goto done;
  }
  /* AWB requires numeric-ID order; table construction above needs lexical. */
  for(unsigned i=1;i<count;i++){PcChange v=changes[i];unsigned j=i;while(j && changes[j-1].index>v.index){changes[j]=changes[j-1];j--;}changes[j]=v;}
  if(!pc_awb(&top,changes,count,reader,ctx,children+7,result,allocated))goto done;
  allocated+=children[7].capacity;
  if(allocated>PC_BANK_MAX_SCRATCH-PC_BANK_MAX_BYTES)goto done;
  if(!pc_rebuild_top(&top,names,children,&final))goto done;
  if(allocated+final.n>result->scratch_peak)result->scratch_peak=allocated+final.n;
  if(result->scratch_peak>PC_BANK_MAX_SCRATCH)goto done;
  result->data=final.p;result->size=(uint32_t)final.n;final.p=NULL;result->cue_count=count;ok=1;
done:
  for(unsigned i=0;i<8;i++)free(children[i].p);
  free(final.p);
  if(!ok)pc_bank_free(result);
  return ok;
}
#endif
