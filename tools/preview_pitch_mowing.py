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


def preview(output, stadium=None):
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
  for(int y=0;y<272;y++)for(int x=0;x<432;x++) {
   vec3 c=nxPitchMowing(vec3(.033,.09,.009),vec3(-5400+x*25,-3400+y*25,0));
   printf("%.6f %.6f %.6f\n",c.r,c.g,c.b);
  }
 }
}
''')
        subprocess.run([compiler, '-std=c++17', '-O2', str(source), '-o', str(binary)],
                       check=True, capture_output=True)
        values = subprocess.check_output([str(binary)])
    linear = np.loadtxt(BytesIO(values)).reshape(6, 272, 432, 3)
    srgb = np.where(linear <= .0031308, linear * 12.92,
                    1.055 * np.power(linear, 1 / 2.4) - .055)
    labels = ('Anfield Stadium — narrow transverse', 'Etihad Stadium — checker',
              'Signal Iduna Park — 18 stripes / native paint alignment', 'Stamford Bridge — narrow vertical / worn grass',
              'Old Trafford — 20 stripes / native paint alignment', 'Camp Nou — small center / native circle alignment')
    indices = [dict(zip((1,2,8,9,12,13),range(6)))[stadium]] if stadium is not None else list(range(6))
    fig, axes = plt.subplots(1 if stadium is not None else 2, 1 if stadium is not None else 3,
                             figsize=(12,8) if stadium is not None else (15,7.5),
                             layout='constrained', facecolor='#16211e')
    for index, ax in zip(indices, np.atleast_1d(axes).flat):
        image, label = srgb[index], labels[index]
        ax.imshow(np.clip(image, 0, 1), origin='lower', extent=(-54, 54, -34, 34))
        line = dict(edgecolor='#e6eee7', facecolor='none', linewidth=.9)
        # Signal Iduna/Old Trafford follow the retained mesh/paint UV audit.
        # Draw those observed fronts, not regulation boxes that are offset by
        # up to 0.28 m in the native artwork. Other previews keep their grid.
        goal, penalty, six_yard = (52.552, 36.22, 47.257) if index in (2, 4) else (52.5, 36, 47)
        ax.add_patch(Rectangle((-goal, -34), goal*2, 68, **line))
        ax.plot([0, 0], [-34, 34], color='#e6eee7', linewidth=.9)
        # Native paint is slightly smaller/offset from regulation dimensions.
        # Camp Nou's second mowing edge follows this actual white circle.
        circle_center, circle_radius = ((.01443, .00962), 9.012) if index == 5 else ((0, 0), 9.15)
        ax.add_patch(Circle(circle_center, circle_radius, **line))
        for side in (-1, 1):
            x = -goal if side < 0 else penalty
            ax.add_patch(Rectangle((x, -20.16), goal-penalty, 40.32, **line))
            x = -goal if side < 0 else six_yard
            ax.add_patch(Rectangle((x, -9.16), goal-six_yard, 18.32, **line))
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
    fig.supxlabel('Distinct stadium stripe widths; shared green and wear. Lighting and native fine detail are not simulated.',
                  color='#c1cec5', fontsize=10)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--stadium', type=int, choices=(1,2,8,9,12,13))
    args=parser.parse_args()
    preview(args.output,args.stadium)
