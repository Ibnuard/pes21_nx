"""Register an eye-template pair to a different source head before local fitting.

The shared head-frame translation preserves interocular spacing. Independent
socket/scale/depth checks and the final visible-aperture gaze audit still apply.
"""
import numpy as np
from realface_eye_fit import sphere, fit_socket


def register_pair(points, guide, *, skin_surface=False, edge_outlier_fallback=False):
    points=np.asarray(points,dtype=float)
    deltas=[];targets=[]
    for sign,side in ((-1,'negative_x'),(1,'positive_x')):
        samples=points[points[:,0]*sign>0]
        center,radius,_=sphere(samples)
        rim=np.asarray(guide[side],dtype=float)
        if rim.ndim!=2 or rim.shape[1]!=3 or len(rim)<8 or not np.isfinite(rim).all():
            raise ValueError('Pair registration needs both finite eyelid guides')
        rough=(rim.min(0)+rim.max(0))/2-center
        rough[1]-=radius
        # Obtain the socket target using the same scale/depth rules as the
        # final fitter, with a temporary front pole, not a guessed iris UV.
        _,_,report=fit_socket(samples+rough,center+rough+[0,radius,0],rim,
                             skin_surface=skin_surface,edge_outlier_fallback=edge_outlier_fallback)
        target=np.asarray(report['target_center_cm'])
        if not (1.5<sign*target[0]<4.8 and 8<target[1]<19 and 165<target[2]<175):
            raise ValueError('Registered socket lies outside the head contract')
        targets.append(target);deltas.append(target-center)
    separation=targets[1]-targets[0]
    if not (4<separation[0]<8.5 and abs(separation[1])<1 and abs(separation[2])<.65):
        raise ValueError('Eyelid guides do not describe a consistent eye pair')
    shared=np.mean(deltas,axis=0)
    residual=max(np.linalg.norm(d-shared) for d in deltas)
    # A measured bilateral skin recess can establish a higher source head
    # frame, but only when both sockets agree within 3.5 mm.
    vertical_limit=3.5 if skin_surface and residual<=.35 else 2.5
    if (np.linalg.norm(shared)>3.5 or abs(shared[0])>.8 or abs(shared[1])>3.2 or abs(shared[2])>vertical_limit
            or residual>1.5):
        raise ValueError('Eye template head-frame registration exceeds bounds: '+str(dict(shared=shared.tolist(),deltas=[d.tolist() for d in deltas],targets=[t.tolist() for t in targets])))
    if max(np.linalg.norm(d) for d in deltas)<=1.5:
        shared=np.zeros(3)  # Keep the already supported local-fitting route.
    return shared,dict(method='paired_head_frame_translation',translation_cm=shared.tolist(),
                       measured_socket_centers_cm=[p.tolist() for p in targets])
