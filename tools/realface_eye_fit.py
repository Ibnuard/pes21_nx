"""Geometry-only eye fitting from each source face's eyelid occlusion rim.

The rim is a fitting reference, never rendered. No player-specific translation
or yaw is hidden here. Reject uncertain shapes instead of exporting bad eyes.
"""
import math
import numpy as np


def sphere(points):
    p = np.asarray(points, dtype=float)
    if p.ndim != 2 or p.shape[1] != 3 or len(p) < 12 or not np.isfinite(p).all():
        raise ValueError('Eye requires finite 3D sphere samples')
    # Centring the equations avoids precision loss at a 170 cm head height.
    mean = p.mean(axis=0); q = p-mean
    result, _, rank, _ = np.linalg.lstsq(np.c_[2*q,np.ones(len(q))], (q*q).sum(axis=1), rcond=None)
    if rank != 4:
        raise ValueError('Eye sphere is degenerate')
    center = result[:3]+mean
    radius = math.sqrt(result[3]+float(result[:3]@result[:3]))
    rms = float(np.sqrt(np.mean((np.linalg.norm(p-center,axis=1)-radius)**2)))
    if not .7 < radius < 2.2 or rms > .12:
        raise ValueError('Eye shape is outside the sphere-fit contract')
    return center, radius, rms


def pupil_position(points, uv, faces, landmark, frontmost=False):
    """Interpolate a texture landmark; do not confuse atlas centre with iris."""
    p=np.asarray(points,dtype=float);st=np.asarray(uv,dtype=float);target=np.asarray(landmark,dtype=float)
    found=[]
    for f in faces:
        if len(f)!=3:raise ValueError('Eye landmark needs triangles')
        a,b,c=st[list(f)]
        system=np.column_stack((b-a,c-a))
        if abs(np.linalg.det(system))<1e-10:continue
        v,w=np.linalg.solve(system,target-a)
        if min(v,w,1-v-w)>=-1e-5:
            found.append((1-v-w)*p[f[0]]+v*p[f[1]]+w*p[f[2]])
    if not found:
        raise ValueError('Pupil texture landmark missing or ambiguous')
    if frontmost:
        return max(found,key=lambda q:q[1])
    if max(np.linalg.norm(q-found[0]) for q in found)>.01:
        raise ValueError('Pupil texture landmark missing or ambiguous')
    return np.mean(found,axis=0)


def radial_atlas_pupil(points, uv):
    """Native atlas V encodes radius, U wraps around the iris.

    The maximum Blender V (minimum source image V) collapses to one 3D
    pole. Sampling the middle of its UV rectangle selects an iris edge and
    creates false gaze corrections. Validate that the seam vertices really
    coincide before using this layout.
    """
    p=np.asarray(points,dtype=float);st=np.asarray(uv,dtype=float)
    if (p.ndim!=2 or p.shape[1]!=3 or st.shape!=(len(p),2) or
            not len(p) or not np.isfinite(p).all() or not np.isfinite(st).all()):
        raise ValueError('Native pupil requires finite positions and UVs')
    pole=p[np.abs(st[:,1]-st[:,1].max())<1e-6]
    if len(pole)<2 or np.max(np.linalg.norm(pole-pole.mean(axis=0),axis=1))>.01:
        raise ValueError('Native eye atlas has no unique radial pupil pole')
    return pole.mean(axis=0)


def rotation_between(before, after):
    a=np.asarray(before,dtype=float);b=np.asarray(after,dtype=float)
    if (a.shape!=(3,) or b.shape!=(3,) or not np.isfinite(a).all() or
            not np.isfinite(b).all() or min(np.linalg.norm(a),np.linalg.norm(b))<1e-8):
        raise ValueError('Pupil direction must be finite and nonzero')
    a=a/np.linalg.norm(a);b=b/np.linalg.norm(b)
    cross=np.cross(a,b);cosine=float(np.clip(a@b,-1,1))
    if cosine < -.99:raise ValueError('Back-facing pupil')
    skew=np.array([[0,-cross[2],cross[1]],[cross[2],0,-cross[0]],[-cross[1],cross[0],0]])
    return np.eye(3)+skew+skew@skew/(1+cosine),math.degrees(math.acos(cosine))


def fit_socket(points, pupil, rim, *, skin_surface=False, edge_outlier_fallback=False):
    points=np.asarray(points,dtype=float);rim=np.asarray(rim,dtype=float)
    center,radius,rms=sphere(points)
    if rim.ndim!=2 or rim.shape[1]!=3 or len(rim)<8 or not np.isfinite(rim).all():
        raise ValueError('Eyelid rim is missing or non-finite')
    low,high=rim.min(axis=0),rim.max(axis=0)
    width,height=high[0]-low[0],high[2]-low[2]
    if not 1.4<width<3.5 or not .25<height<1.65:
        raise ValueError('Eyelid opening requires review')
    target=(low+high)/2
    radial=(rim[:,0]-target[0])**2+(rim[:,2]-target[2])**2
    # The globe must contain the rim laterally. Keep its original size whenever
    # possible, allowing at most 15% growth, with no arbitrary global shrinking.
    target_radius=max(radius,math.sqrt(float(radial.max()))*1.025)
    scale=target_radius/radius
    if scale>1.15:raise ValueError('Eyelid opening needs excessive eye scaling')
    depths=rim[:,1]-np.sqrt(target_radius**2-radial)
    target[1]=np.median(depths)
    depth_rms=float(np.sqrt(np.mean((depths-target[1])**2)))
    raw_depth_rms=depth_rms;discarded=[]
    if depth_rms>.32 and skin_surface and edge_outlier_fallback:
        # The tear-duct wall is skin, but not part of a spherical globe. Only
        # isolated depth outliers at the lateral ends can leave the depth fit.
        # Retain the FULL bounds/radius and optical aperture; never trim the
        # rendered mesh, enlarge it further or waive noisy central samples.
        edge=(rim[:,0]<low[0]+width*.2)|(rim[:,0]>high[0]-width*.2)
        bad=np.abs(depths-target[1])>.65
        discarded=np.flatnonzero(bad).tolist()
        if (not discarded or np.any(bad & ~edge) or bad.sum()>len(rim)*.15):
            raise ValueError('Unstable skin depth is not limited to isolated tear-duct samples')
        support=rim[~bad]
        measured_center=(support.min(0)+support.max(0))/2
        if np.linalg.norm(measured_center[[0,2]]-target[[0,2]])>.25:
            raise ValueError('Tear-duct cleanup shifts the measured socket too far')
        target[[0,2]]=measured_center[[0,2]]
        support_radial=(support[:,0]-target[0])**2+(support[:,2]-target[2])**2
        if np.max(support_radial)>=target_radius**2:
            raise ValueError('Cleaned skin support exceeds the unchanged globe radius')
        depths=support[:,1]-np.sqrt(target_radius**2-support_radial)
        target[1]=np.median(depths)
        depth_rms=float(np.sqrt(np.mean((depths-target[1])**2)))
    if depth_rms>.32:raise ValueError('Eyelid rim does not support a stable globe depth')
    median_depth=float(target[1])
    if skin_surface:
        # A skin rim encloses the globe; fitting through its median can put
        # half of the globe boundary in front of the lower eyelid. Use the
        # conservative measured depth, tolerating a few noisy rim samples.
        # This is a surface constraint, not a fixed per-player translation.
        target[1]=float(np.quantile(depths,.15))
        if median_depth-target[1]>.45:
            raise ValueError('Skin rim needs excessive eye depth clearance')
    translation=float(np.linalg.norm(target-center))
    if translation>1.5:raise ValueError('Eye placement differs too far from source')
    # Rest gaze is straight forward through the centre of this eyelid opening.
    rotation,degrees=rotation_between(np.asarray(pupil)-center,[0,1,0])
    if degrees>15:raise ValueError('Pupil gaze exceeds automatic correction limit')
    fitted=(points-center)@rotation.T*scale+target
    fitted_pupil=(np.asarray(pupil)-center)@rotation.T*scale+target
    if abs(fitted_pupil[0]-target[0])>.001 or abs(fitted_pupil[2]-target[2])>.001:
        raise ValueError('Pupil failed to centre in the eyelid')
    return fitted,rotation,dict(method='source_eyelid_rim',sphere_fit_rms_cm=rms,
        rim_depth_rms_cm=depth_rms,source_center_cm=center.tolist(),target_center_cm=target.tolist(),
        raw_rim_depth_rms_cm=raw_depth_rms,excluded_tear_duct_samples=discarded,
        scale=scale,translation_cm=translation,gaze_degrees=degrees,
        depth_policy='skin_enclosure_quantile_15' if skin_surface else 'helper_median',
        depth_clearance_cm=median_depth-float(target[1]),
        final_rim_depth_rms_cm=float(np.sqrt(np.mean((depths-target[1])**2))),
        opening_width_cm=float(width),opening_height_cm=float(height),
        pupil_after_cm=fitted_pupil.tolist())


def verified_source_pair(source):
    """A complete, nearly spherical anatomical source pair can size a template.

    This evidence is stronger than extrapolating a sphere from sparse eyelids.
    It never authorizes enlarged eyes from a guide or a single source globe.
    """
    if set(source)!={'negative_x','positive_x'}:return False
    try:
        a,ra,ea=sphere(source['negative_x']);b,rb,eb=sphere(source['positive_x'])
    except ValueError:return False
    return bool(-4.8<a[0]<-1.5 and 1.5<b[0]<4.8 and 4<b[0]-a[0]<8.5
                and all(8<p[1]<19 and 165<p[2]<175 for p in (a,b))
                and abs(a[1]-b[1])<.6 and abs(a[2]-b[2])<.4
                and .95<min(ra,rb) and max(ra,rb)<1.8 and max(ra,rb)/min(ra,rb)<1.12
                and max(ea,eb)<.03)


def fit_source_globe(points, pupil, source, *, measured_pair=False):
    """Use this player's actual source eyeball when an occlusion guide is absent.

    The neutral atlas remains explicit. Both globe shapes must pass the sphere
    contract; visible-aperture ray tests still run after this registration.
    """
    points = np.asarray(points, dtype=float)
    center, radius, rms = sphere(points)
    target, target_radius, target_rms = sphere(source)
    if not (1.5 < abs(target[0]) < 4.8 and 8 < target[1] < 19 and 165 < target[2] < 175):
        raise ValueError('Source eyeball lies outside the head contract')
    scale = target_radius / radius
    if not .8 < scale < (1.5 if measured_pair and target_rms<.03 and .95<target_radius<1.8 else 1.25):
        raise ValueError('Source eyeball requires excessive template scale')
    rotation, degrees = rotation_between(np.asarray(pupil)-center, [0,1,0])
    if degrees > 15:
        raise ValueError('Source pupil gaze exceeds automatic correction limit')
    fitted = (points-center) @ rotation.T * scale + target
    fitted_pupil = (np.asarray(pupil)-center) @ rotation.T * scale + target
    return fitted, rotation, dict(method='own_source_eyeball_geometry',
        sphere_fit_rms_cm=rms, target_sphere_fit_rms_cm=target_rms,
        source_pair_size_verified=measured_pair,
        source_center_cm=center.tolist(), target_center_cm=target.tolist(),
        scale=scale, translation_cm=float(np.linalg.norm(target-center)),
        gaze_degrees=degrees, pupil_after_cm=fitted_pupil.tolist())
