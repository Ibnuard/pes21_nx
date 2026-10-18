"""Separate interior exposed scalp from loss of fine silhouette strands."""
import numpy as np


def neighbourhood(mask,operation):
    padded=np.pad(np.asarray(mask,bool),1)
    h,w=mask.shape
    return operation.reduce([padded[y:y+h,x:x+w] for y in range(3) for x in range(3)])


def compare_visibility(original,prepared,prepared_skin):
    # Closing joins tiny source strand gaps; erosion then excludes the hairline
    # and isolated tips. Missing hair here exposes scalp inside the hairstyle.
    envelope=neighbourhood(neighbourhood(original,np.logical_or),np.logical_and)
    interior=neighbourhood(neighbourhood(envelope,np.logical_and),np.logical_and)
    bald=interior & prepared_skin & ~prepared
    missing=original & ~prepared
    return dict(reference_pixels=int(original.sum()),interior_pixels=int(interior.sum()),
        visible_missing_pixels=int(missing.sum()),interior_bald_pixels=int(bald.sum()),
        visible_missing_ratio=float(missing.sum()/max(original.sum(),1)),
        interior_bald_ratio=float(bald.sum()/max(interior.sum(),1)))
