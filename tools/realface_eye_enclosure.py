"""Choose a bounded eye depth from actual skin occlusion, not player offsets."""
import numpy as np


def choose_depth(eye_depth,skin_depth,opening,pupil):
    eye=np.asarray(eye_depth,float);skin=np.asarray(skin_depth,float)
    opening=np.asarray(opening,bool);pupil=np.asarray(pupil,bool)
    if eye.shape!=skin.shape or eye.shape!=opening.shape or eye.shape!=pupil.shape:
        raise ValueError('Eye enclosure grids differ')
    if opening.sum()<30 or pupil.sum()<3:raise ValueError('Insufficient orbital evidence')
    live=np.isfinite(eye);candidates=[]
    for shift in np.linspace(0,.8,33):
        visible=live&(eye-shift>skin+.005)
        inside=int((visible&opening).sum());spill=int((visible&~opening).sum())
        pupil_fraction=float((visible&pupil).sum()/pupil.sum())
        row=dict(depth_shift_cm=float(shift),inside_pixels=inside,spill_pixels=spill,
                 spill_fraction=spill/max(inside+spill,1),pupil_visible_fraction=pupil_fraction)
        candidates.append(row)
        if spill<=max(2,inside*.012) and inside>=opening.sum()*.4 and pupil_fraction>=.9:
            return row,dict(before=candidates[0],after=row,max_depth_shift_cm=.8)
    raise ValueError('No bounded eye depth encloses the globe while keeping the pupil visible')
