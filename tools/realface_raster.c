/* Offline diagnostic raster accelerator. No runtime/game dependency or CRT. */
#if defined(_WIN32)
#define API __declspec(dllexport)
#else
#define API
#endif
typedef long long i64;
static int below(double v) { int n=(int)v; return n-(v<n); }
static int above(double v) { int n=(int)v; return n+(v>n); }
static int bound(int v,int max) { return v<0?0:v>max?max:v; }
static double repeat(double v) { return v>=0 && v<=1?v:v-below(v); }
API void face_raster(const double *p,const i64 *tri,const double *uv,const double *alpha,
    int count,int aw,int ah,int size,const double *lo,const double *hi,const double *skin,
    double *depth,i64 *front,unsigned short *opaque,unsigned short *cards)
{
    for(int f=0;f<count;f++) {
        const double *a=p+3*tri[3*f],*b=p+3*tri[3*f+1],*c=p+3*tri[3*f+2];
        double ax=(a[0]-lo[0])/(hi[0]-lo[0])*size,ay=(a[1]-lo[1])/(hi[1]-lo[1])*size;
        double bx=(b[0]-lo[0])/(hi[0]-lo[0])*size,by=(b[1]-lo[1])/(hi[1]-lo[1])*size;
        double cx=(c[0]-lo[0])/(hi[0]-lo[0])*size,cy=(c[1]-lo[1])/(hi[1]-lo[1])*size;
        double lx=ax<bx?ax:bx,hx=ax>bx?ax:bx,ly=ay<by?ay:by,hy=ay>by?ay:by;
        lx=lx<cx?lx:cx;hx=hx>cx?hx:cx;ly=ly<cy?ly:cy;hy=hy>cy?hy:cy;
        int x0=below(lx),x1=above(hx),y0=below(ly),y1=above(hy);
        if(x0<0)x0=0;if(y0<0)y0=0;if(x1>=size)x1=size-1;if(y1>=size)y1=size-1;
        double den=(by-cy)*(ax-cx)+(cx-bx)*(ay-cy);
        if(den>-1e-10 && den<1e-10)continue;
        const double *t=uv+6*f;
        for(int y=y0;y<=y1;y++)for(int x=x0;x<=x1;x++) {
            double w0=((by-cy)*(x+.5-cx)+(cx-bx)*(y+.5-cy))/den;
            double w1=((cy-ay)*(x+.5-cx)+(ax-cx)*(y+.5-cy))/den,w2=1-w0-w1;
            if(w0 < -1e-7 || w1 < -1e-7 || w2 < -1e-7)continue;
            int i=y*size+x;cards[i]++;
            double u=repeat((w0*t[0]+w1*t[2])+w2*t[4]),v=repeat((w0*t[1]+w1*t[3])+w2*t[5]);
            int tx=bound((int)(u*aw),aw-1),ty=bound((int)(v*ah),ah-1);
            if(alpha[ty*aw+tx]<.333)continue;
            opaque[i]++;
            double z=(w0*a[2]+w1*b[2])+w2*c[2];
            if(z>depth[i] && (!skin || z>skin[i]+.005)) {depth[i]=z;front[i]=f;}
        }
    }
}
