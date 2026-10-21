"""Preview the exact authored pitch mowing math without game assets.

Diagnostic top views only: these are not game renders or FPS measurements.
Requires a host C++ compiler, numpy and matplotlib.
"""
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
    from matplotlib.patches import Arc, Circle, Rectangle

    compiler = shutil.which('g++')
    if not compiler:
        raise RuntimeError('Host C++ compiler unavailable')
    with tempfile.TemporaryDirectory(prefix='pesnx-mowing-preview-') as directory:
        source = Path(directory) / 'mowing.cpp'
        binary = source.with_suffix('.exe')
        source.write_text(host_math() + r'''
int main() {
 const int ids[]={1,2,8,9,12,13};
 for(int i=0;i<6;i++) {
  nxStadiumProfile=ids[i];
  for(int y=0;y<272;y++)for(int x=0;x<420;x++) {
   vec3 c=nxPitchMowing(vec3(.033,.09,.009),vec3(-5250+x*25,-3400+y*25,0));
   printf("%.6f %.6f %.6f\n",c.r,c.g,c.b);
  }
 }
}
''')
        subprocess.run([compiler, '-std=c++17', '-O2', str(source), '-o', str(binary)],
                       check=True, capture_output=True)
        values = subprocess.check_output([str(binary)])
    linear = np.loadtxt(BytesIO(values)).reshape(6, 272, 420, 3)
    srgb = np.where(linear <= .0031308, linear * 12.92,
                    1.055 * np.power(linear, 1 / 2.4) - .055)
    labels = ('Anfield Stadium — narrow transverse', 'Etihad Stadium — checker',
              'Signal Iduna Park — broad transverse', 'Stamford Bridge — longitudinal',
              'Old Trafford — straight alternating', 'Camp Nou — concentric rings')
    fig, axes = plt.subplots(2, 3, figsize=(15, 7.5), layout='constrained', facecolor='#16211e')
    for image, label, ax in zip(srgb, labels, axes.flat):
        ax.imshow(np.clip(image, 0, 1), origin='lower', extent=(-52.5, 52.5, -34, 34))
        line = dict(edgecolor='#e6eee7', facecolor='none', linewidth=.9)
        ax.add_patch(Rectangle((-52.5, -34), 105, 68, **line))
        ax.plot([0, 0], [-34, 34], color='#e6eee7', linewidth=.9)
        ax.add_patch(Circle((0, 0), 9.15, **line))
        for side in (-1, 1):
            x = -52.5 if side < 0 else 36
            ax.add_patch(Rectangle((x, -20.16), 16.5, 40.32, **line))
            x = -52.5 if side < 0 else 47
            ax.add_patch(Rectangle((x, -9.16), 5.5, 18.32, **line))
            ax.plot([side * 41.5], [0], '.', color='#e6eee7', markersize=2)
            theta = (-53, 53) if side < 0 else (127, 233)
            ax.add_patch(Arc((side * 41.5, 0), 18.3, 18.3,
                             theta1=theta[0], theta2=theta[1],
                             color='#e6eee7', linewidth=.9))
        ax.set(title=label, xlim=(-54, 54), ylim=(-35.5, 35.5))
        ax.set_facecolor('#16211e')
        ax.title.set(color='#edf5ed', fontsize=11)
        ax.set_axis_off()
    fig.suptitle('Authored pitch mowing — exact shader math, diagnostic top views',
                 color='#edf5ed', fontsize=16)
    fig.supxlabel('Konami retains its accepted original bands. Lighting, weather and fine detail are not simulated.',
                  color='#c1cec5', fontsize=10)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    preview(parser.parse_args().output)
