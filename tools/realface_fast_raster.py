"""Optional, independently tested native acceleration of offline raster checks."""
import ctypes
import numpy as np


def load(path):
    library=ctypes.CDLL(str(path))
    call=library.face_raster
    call.argtypes=[ctypes.c_void_p]*4+[ctypes.c_int]*4+[ctypes.c_void_p]*7
    call.restype=None

    def raster(positions,triangles,uv,alpha,basis,bounds=None,size=72,skin_depth=None):
        p=np.ascontiguousarray(np.asarray(positions)@basis.T,dtype=np.float64)
        tri=np.ascontiguousarray(triangles,dtype=np.int64)
        coords=np.ascontiguousarray(uv,dtype=np.float64)
        texture=np.ascontiguousarray(alpha,dtype=np.float64)
        if bounds is None: bounds=(p[:,:2].min(axis=0)-.15,p[:,:2].max(axis=0)+.15)
        lo,hi=(np.ascontiguousarray(v,dtype=np.float64) for v in bounds)
        depth=np.full((size,size),-np.inf);front=np.full((size,size),-1,dtype=np.int64)
        opaque=np.zeros((size,size),np.uint16);cards=np.zeros_like(opaque)
        skin=None if skin_depth is None else np.ascontiguousarray(skin_depth,dtype=np.float64)
        pointer=lambda a:None if a is None else a.ctypes.data
        call(*map(pointer,(p,tri,coords,texture)),len(tri),texture.shape[1],texture.shape[0],size,
             *map(pointer,(lo,hi,skin,depth,front,opaque,cards)))
        return dict(front=front,mask=front>=0,opaque=opaque,cards=cards,bounds=bounds,depth=depth,
                    **({} if skin_depth is None else {'skin_depth':skin_depth}))
    # Keep the loaded library alive with the callable, including on Windows.
    raster.library=library
    return raster
