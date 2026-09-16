"""Project-authored 3D jersey, UV coordinates, and orthographic CPU renderer.

Coordinates use a 128-unit frame with depth facing the camera. Each triangle
owns UVs, is depth-tested, and is lit from its interpolated surface normal.
No old thumbnail silhouette or kit-specific colour repaint is used.
"""
from dataclasses import dataclass
from pathlib import Path
import math

import numpy as np
from PIL import Image


RENDERER_VERSION = "uniform16_mesh_v5"


@dataclass
class Mesh:
    vertices: np.ndarray
    uv: np.ndarray
    normals: np.ndarray
    triangles: np.ndarray
    parts: list[str]


def build_mesh() -> Mesh:
    vertices, coords, normals, triangles, parts = [], [], [], [], []

    def surface(name, function, columns=20, rows=20):
        start = len(vertices)
        for j in range(rows + 1):
            for i in range(columns + 1):
                s, t = i / columns, j / rows
                xyz, uv = function(s, t)
                eps = .0001
                ds = np.asarray(function(min(1, s+eps), t)[0]) - np.asarray(function(max(0, s-eps), t)[0])
                dt = np.asarray(function(s, min(1, t+eps))[0]) - np.asarray(function(s, max(0, t-eps))[0])
                normal = np.cross(ds, dt)
                normal /= max(np.linalg.norm(normal), 1e-12)
                if normal[2] < 0:
                    normal *= -1
                vertices.append(xyz)
                coords.append(uv)
                normals.append(normal)
        for j in range(rows):
            for i in range(columns):
                a = start + j * (columns+1) + i
                triangles.extend([(a,a+1,a+columns+2),(a,a+columns+2,a+columns+1)])
                parts.extend([name,name])

    def torso(s, t):
        width = 30 - 3*math.sin(math.pi*t) + t
        x = 64 + (s*2-1)*width
        y = 26 + 92*t
        depth = 5 + 5 * math.sin(math.pi*s)
        depth += .4*math.sin(6*math.pi*s + t*2)*math.sin(math.pi*t)
        return (x,y,depth), (88+80*s,200+151*t)
    surface("front", torso, 28, 32)

    # The front shirt is in the lower half of Uniform16. Shoulder graphics
    # beside the collar must travel outward onto the rounded sleeve cap.
    for side in (-1,1):
        reflect = lambda x: 64+side*(x-64)
        atlas_x = lambda u: 128+side*(u-128)
        # One continuous surface from neck to cuff: splitting the shoulder
        # and sleeve into unrelated quads introduced a UV jump and a hard
        # lighting seam directly through the stripes.
        def sleeve(s, t):
            # Curved upper/lower edges, with a rounded shoulder cap.
            upper_x = 75 + 42*s - 7*s*s
            upper_y = 8 + 7*s + 29*s*s
            lower_x = 75 + 29*s - 10*s*s
            lower_y = 26 + 27*s
            x = upper_x*(1-t) + lower_x*t
            y = upper_y*(1-t) + lower_y*t
            z = (5+4*t)*(1-s) + 2*s
            z += 3*math.sin(math.pi*s)*math.sin(math.pi*t)
            # Continuous UVs, including the sleeve emblem beyond the stripes.
            u = 141 + (51-24*t)*s
            v = 174 + 26*t + (38-23*t)*s*s
            return (reflect(x),y,z), (atlas_x(u),v)
        surface("sleeve_left" if side == -1 else "sleeve_right", sleeve, 40, 24)

    # Chest joins the collar below its front edge. The neck hole is geometry;
    # the circular atlas patch is never painted as a badge on the chest.
    def upper_chest(s,t):
        local = 2*s-1
        arc = math.sqrt(max(0,1-local*local))
        top_y = 12+8*arc
        top_v = 183+15*arc
        x = (53+22*s)*(1-t)+(34+60*s)*t
        source_u = (115+26*s)*(1-t)+(88+80*s)*t
        return (x,top_y+(26-top_y)*t,5+5*math.sin(math.pi*s)), (source_u,top_v+(200-top_v)*t)
    surface("upper_chest",upper_chest,40,12)

    def collar(s,t):
        angle = s*2*math.pi
        rx, ry = 11-1.8*t, 8-1.8*t
        return ((64+rx*math.cos(angle),12+ry*math.sin(angle),
                 11+1.3*t),
                (128+(13-2*t)*math.cos(angle),183+(15-2*t)*math.sin(angle)))
    surface("collar",collar,64,4)
    return Mesh(np.asarray(vertices),np.asarray(coords),np.asarray(normals),
                np.asarray(triangles,dtype=np.int32),parts)


def render_mesh(atlas: Image.Image, mesh: Mesh | None = None, size=128) -> Image.Image:
    if atlas.size != (256,384):
        raise ValueError("expected 256x384 Uniform16 atlas")
    mesh = mesh or build_mesh()
    scale = 4
    dimension = size*scale
    factor = dimension/128
    pixels = np.zeros((dimension,dimension,4),dtype=np.uint8)
    depth = np.full((dimension,dimension),-np.inf)
    texture = np.asarray(atlas.convert("RGBA"),dtype=float)
    positions = mesh.vertices[:,:2]*factor
    light = np.array([-.3,-.4,.8660254])
    for tri in mesh.triangles:
        p = positions[tri]
        low = np.maximum(np.floor(p.min(axis=0)).astype(int),0)
        high = np.minimum(np.ceil(p.max(axis=0)).astype(int),dimension-1)
        if np.any(high < low):
            continue
        x,y = np.meshgrid(np.arange(low[0],high[0]+1)+.5,np.arange(low[1],high[1]+1)+.5)
        denominator = (p[1,1]-p[2,1])*(p[0,0]-p[2,0])+(p[2,0]-p[1,0])*(p[0,1]-p[2,1])
        if abs(denominator)<1e-9:
            continue
        a=((p[1,1]-p[2,1])*(x-p[2,0])+(p[2,0]-p[1,0])*(y-p[2,1]))/denominator
        b=((p[2,1]-p[0,1])*(x-p[2,0])+(p[0,0]-p[2,0])*(y-p[2,1]))/denominator
        weights=np.stack((a,b,1-a-b),axis=-1)
        z=weights@mesh.vertices[tri,2]
        region=np.s_[low[1]:high[1]+1,low[0]:high[0]+1]
        visible=(weights.min(axis=-1)>=-1e-7)&(z>depth[region])
        if not visible.any():
            continue
        uv=weights@mesh.uv[tri]
        u=np.clip(uv[...,0],0,255); v=np.clip(uv[...,1],0,383)
        u0=u.astype(int); v0=v.astype(int); u1=np.minimum(u0+1,255); v1=np.minimum(v0+1,383)
        fu=(u-u0)[...,None]; fv=(v-v0)[...,None]
        sampled=(texture[v0,u0]*(1-fu)+texture[v0,u1]*fu)*(1-fv)+(texture[v1,u0]*(1-fu)+texture[v1,u1]*fu)*fv
        normal=weights@mesh.normals[tri]
        normal/=np.maximum(np.linalg.norm(normal,axis=-1,keepdims=True),1e-8)
        shade=.72+.28*np.clip(normal@light,0,1)
        sampled[...,:3]*=shade[...,None]
        pixels[region][visible]=np.clip(sampled[visible],0,255).astype(np.uint8)
        depth[region][visible]=z[visible]
    return Image.fromarray(pixels).resize((size,size),Image.Resampling.LANCZOS)


def export_obj(path: Path, mesh: Mesh | None = None):
    mesh=mesh or build_mesh()
    lines=["# Project-authored preview mesh. UV uses the 256x384 Uniform16 atlas."]
    lines += [f"v {x:.6f} {-y:.6f} {z:.6f}" for x,y,z in mesh.vertices]
    lines += [f"vt {u/256:.8f} {1-v/384:.8f}" for u,v in mesh.uv]
    for part,triangle in zip(mesh.parts,mesh.triangles):
        lines.append(f"g {part}")
        lines.append("f "+" ".join(f"{i+1}/{i+1}" for i in triangle))
    path.write_text("\n".join(lines)+"\n",encoding="utf-8")
