"""Opt-in source-eye/seam-safe worker for joined hair-volume experiments."""
from pathlib import Path
import runpy
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import blender_realface_mobile as mobile
import blender_realface_source_quality as source
import blender_realface_hair_volume as volume

original_prepare=mobile.prepare_hair
original_normals=source.transfer_normals


def prepare(obj,job,native,cooked):
    volume.LAST_SURFACE=None
    if job['budgets'].get('hair_mode')!='alpha_volume':
        return original_prepare(obj,job,native,cooked)
    if not job['budgets'].get('source_eye'):
        raise ValueError('Volume worker requires the explicit source-quality face policy')
    return volume.prepare(obj,job,native,cooked)


def normals(obj,native,cooked,original):
    return original_normals(obj,native,cooked,volume.LAST_SURFACE if volume.LAST_SURFACE is not None else original)


mobile.prepare_hair=prepare
source.transfer_normals=normals
runpy.run_path(str(Path(__file__).with_name('blender_realface_seam_worker.py')),run_name='__main__')
