"""Compact scalp coverage; keep the source hairline, fill interior strand gaps."""
import numpy as np


def solid_scalp_mask(alpha):
    """Rows run from crown to hairline; columns wrap around the head.

    Fill behind the last opaque sample of each occupied azimuth. Do not
    extend the lower hairline or invent hair at wholly empty azimuths.
    Facial hair is a separate region and must never use this operation.
    """
    mask = np.asarray(alpha) >= .333
    if mask.ndim != 2 or not mask.any():
        raise ValueError('Scalp envelope needs nonempty 2D coverage')
    rows = np.arange(mask.shape[0])[:, None]
    last = np.max(np.where(mask, rows, -1), axis=0)
    return ((rows <= last) & (last >= 0)).astype(np.float32)
