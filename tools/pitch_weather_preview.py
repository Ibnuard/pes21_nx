"""Plot the shipped pitch weather math on a synthetic pitch, not a game capture."""
import argparse
from io import BytesIO
from pathlib import Path
import shutil
import subprocess
import tempfile
from stadium_lite_preview import host_math


def preview(output):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    cc = shutil.which('g++')
    if not cc:
        raise RuntimeError('Host g++ compiler required')
    with tempfile.TemporaryDirectory(prefix='pesnx-weather-preview-') as directory:
        path = Path(directory)/'preview.cpp'
        exe = path.with_suffix('.exe')
        path.write_text(host_math()+r'''
int main(){
 nxDayStadium=1;
 for(int mode=0;mode<4;mode++)for(int y=0;y<272;y++)for(int x=0;x<420;x++){
  float wx=-5250+x*25,wy=-3400+y*25;
  float stripe=((x/35)%2)?1.08:.96;
  vec3 grass=vec3(.072,.235,.035)*stripe;
  nxStadiumClimate=vec4(mode<2?mode:2,mode==3?1:0,0,mode>1?1:0);
  grass=grass*(nxDirectLight(vec3(1.0),1.0)*.65+nxAmbientLight(vec3(1.0),1.0)*.35);
  vec3 color=nxPitchWeather(grass,vec3(wx,wy,0));
  float alpha=0;
  printf("%.5f %.5f %.5f %.5f\n",color.r,color.g,color.b,alpha);
 }
}
''')
        subprocess.run([cc,'-std=c++17','-O2',str(path),'-o',str(exe)],check=True,capture_output=True)
        values = np.loadtxt(BytesIO(subprocess.check_output([str(exe)]))).reshape(4,272,420,4)
    fig, axes = plt.subplots(2,2,figsize=(12,8),layout='constrained')
    titles = ['Fine / Summer','Cloudy / Summer','Rainy / Summer: wet patches','Rainy / Winter: thin snow remnants']
    for index, ax in enumerate(axes.flat):
        rgb=np.clip(values[index,:,:,:3],0,1)**(1/2.2)
        ax.imshow(rgb,origin='lower',extent=(-52.5,52.5,-34,34))
        ax.plot([-51,51,51,-51,-51],[-32.5,-32.5,32.5,32.5,-32.5],c='white',lw=.7)
        ax.plot([0,0],[-32.5,32.5],c='white',lw=.7)
        ax.add_patch(plt.Circle((0,0),9.15,fill=False,color='white',lw=.7))
        ax.set_title(titles[index]);ax.set_axis_off()
    fig.suptitle('Shader math on synthetic turf — not a Switch screenshot',fontsize=13)
    output.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(output,dpi=125)
    plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    preview(parser.parse_args().output)
