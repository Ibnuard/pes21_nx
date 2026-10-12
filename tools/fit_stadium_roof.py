"""Fit a cheap rounded ring to an offline roof-height grid (numpy/scipy).

The measured plane remains an approximation: terraced or sloping roofs do
not become dynamic shadow maps. Review the fitted mask before promotion.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from scipy import ndimage


def rounded_inside(x, y, extent, radius):
    qx = np.abs(x) - extent[0] + radius
    qy = np.abs(y) - extent[1] + radius
    return (np.maximum(qx, 0)**2 + np.maximum(qy, 0)**2 <= radius**2) & (np.maximum(qx, qy) <= radius)


def fit_grid(heights, separate_centers=False):
    if heights.shape != (291, 351) or not np.isfinite(heights).all():
        raise ValueError('Expected finite one-metre roof grid')
    roof = ndimage.binary_opening(ndimage.binary_closing(heights > 0, iterations=2), iterations=2)
    labels, _ = ndimage.label(~roof)
    hole = labels == labels[145, 175]
    if hole[0].any() or hole[-1].any() or hole[:, 0].any() or hole[:, -1].any():
        raise ValueError('Open-sided roof requires a manually reviewed panel profile')
    labels, count = ndimage.label(roof)
    sizes = np.bincount(labels.ravel()); sizes[0] = 0
    outer = ndimage.binary_fill_holes(labels == sizes.argmax())
    yy, xx = np.mgrid[-145:146, -175:176]
    ys, xs = np.nonzero(hole)
    center = ((xs.max()+xs.min())/2-175, (ys.max()+ys.min())/2-145)
    result = {}
    for name, target in (('inner', hole), ('outer', outer)):
        ys, xs = np.nonzero(target)
        fit_center = ((xs.max()+xs.min())/2-175, (ys.max()+ys.min())/2-145) if separate_centers else center
        extent = [float(max(abs(xs-175-fit_center[0])))+.5, float(max(abs(ys-145-fit_center[1])))+.5]
        candidates = np.arange(0, min(extent)+.1, .5)
        radius = min(candidates, key=lambda r: np.count_nonzero(rounded_inside(xx-fit_center[0], yy-fit_center[1], extent, r) != target))
        predicted = rounded_inside(xx-fit_center[0], yy-fit_center[1], extent, radius)
        result[name] = [v*100 for v in (*extent, float(radius))]
        result[name+'_iou'] = float(np.count_nonzero(predicted & target) / np.count_nonzero(predicted | target))
        if name == 'outer' and separate_centers:
            result['outer_offset'] = [float(fit_center[i]-center[i])*100 for i in range(2)]
    result['center'] = [center[0]*100, center[1]*100, 0., 0.]
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('audit', type=Path)
    p.add_argument('--separate-centers', action='store_true')
    args = p.parse_args()
    report = json.loads(args.audit.read_text())
    fit = fit_grid(np.load(args.audit.with_suffix('.npy')), args.separate_centers)
    if min(fit['inner_iou'], fit['outer_iou']) < .8:
        raise ValueError('Fit needs manual review: ' + str(fit))
    report.setdefault('axis_fit', {k: report[k] for k in ('inner','outer','center')})
    report['inner'] = fit['inner'] + [report['inner'][3]]
    report['outer'] = fit['outer'] + [0.]
    report['center'] = fit['center']
    if args.separate_centers:
        report['outer'][3] = fit['outer_offset'][0]
        report['center'][3] = fit['outer_offset'][1]
    report['fit_iou'] = [fit['inner_iou'], fit['outer_iou']]
    args.audit.write_text(json.dumps(report, indent=2)+'\n')
    print(args.audit.parent.name, report['inner'], report['outer'], report['fit_iou'])


if __name__ == '__main__':
    main()
