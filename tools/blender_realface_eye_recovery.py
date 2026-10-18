"""Wider inner eye caps for source apertures rejected by the conservative cap.

The caller still checks skin spill, original pupil visibility and coverage.
All cap UVs are sampled from the same player's original eye surface.
"""
import math
import numpy as np
from mathutils import Vector


def aperture_cap(center,xs,zs,opening,skin_tree,eye_tree,positions,faces,source_uv,
                 rim_clearance=.025,front_clearance=.03):
    center=np.asarray(center).copy()
    # Pick an interior fan origin near the source pupil if the spherical fit
    # placed it on the eyelid edge. UVs/pupil tests keep their original anchor.
    xi=int(np.argmin(abs(xs-center[0])));zi=int(np.argmin(abs(zs-center[2])))
    if not opening[zi,xi]:
        yy,xx=np.where(opening)
        distance=(xs[xx]-center[0])**2+(zs[yy]-center[2])**2
        i=int(np.argmin(distance))
        if distance[i]>.3**2:raise ValueError('Source pupil too far from the recovered aperture')
        center[0]=xs[xx[i]];center[2]=zs[yy[i]]
    vertices=[];uv=[];triangles=[];segments=24;rings=3
    def eye_hit(x,z):
        hit,_,index,_=eye_tree.ray_cast(Vector((x,40,z)),Vector((0,-1,0)))
        if hit is None:hit,_,index,_=eye_tree.find_nearest(Vector((x,center[1]+1.5,z)))
        a,b,c=(Vector(positions[i]) for i in faces[index]);e0=b-a;e1=c-a;q=hit-a
        aa=e0.dot(e0);ab=e0.dot(e1);bb=e1.dot(e1);den=aa*bb-ab*ab
        if abs(den)<1e-12:raise ValueError('Eye UV projection hit a degenerate face')
        u=(bb*q.dot(e0)-ab*q.dot(e1))/den;v=(aa*q.dot(e1)-ab*q.dot(e0))/den
        return hit,np.array([1-u-v,u,v])@source_uv[index]
    hit,coord=eye_hit(center[0],center[2]);vertices.append((center[0],hit.y-front_clearance,center[2]));uv.append(coord)
    for ring in range(1,rings+1):
        for segment in range(segments):
            angle=segment*2*math.pi/segments;dx=math.cos(angle);dz=math.sin(angle);last=0.
            for radius in np.linspace(0,2.5,501):
                x=center[0]+radius*dx;z=center[2]+radius*dz
                xi=int(np.argmin(abs(xs-x)));zi=int(np.argmin(abs(zs-z)))
                if not opening[zi,xi]:break
                last=float(radius)
            if last<.08:raise ValueError('Recovered pupil lies outside a usable eyelid aperture')
            radius=last*.84 if ring==1 else max(last-.02,.02) if ring==2 else last+.08
            x=center[0]+radius*dx;z=center[2]+radius*dz
            original,coord=eye_hit(x,z)
            skin,_,_,_=skin_tree.ray_cast(Vector((x,40,z)),Vector((0,-1,0)))
            if skin is None:raise ValueError('Missing skin support at recovered eyelid edge')
            y=original.y-front_clearance if ring==1 else skin.y-rim_clearance-(0 if ring==2 else .02)
            vertices.append((x,y,z));uv.append(coord)
    for i in range(segments):triangles.append((0,1+i,1+(i+1)%segments))
    for ring in range(rings-1):
        a=1+ring*segments;b=a+segments
        for i in range(segments):
            j=(i+1)%segments;triangles.extend(((a+i,b+i,a+j),(a+j,b+i,b+j)))
    return vertices,[tuple(reversed(face)) for face in triangles],uv
