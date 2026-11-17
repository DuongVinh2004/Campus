"""Bounded .npy loading: the header is checked against the file size before NumPy allocates."""
from __future__ import annotations

from pathlib import Path

import numpy as np


def load_matrix(path: str | Path) -> np.ndarray:
    path = Path(path)
    with path.open("rb") as stream:
        stream.seek(0, 2)
        size = stream.tell()
        stream.seek(0)
        version = np.lib.format.read_magic(stream)
        if version == (1, 0):
            shape, _, dtype = np.lib.format.read_array_header_1_0(stream)
        elif version == (2, 0):
            shape, _, dtype = np.lib.format.read_array_header_2_0(stream)
        else:
            raise ValueError("INDEX_NPY_VERSION")
        if dtype.hasobject or len(shape) != 2 or any(n < 0 for n in shape):
            raise ValueError("INDEX_NPY_HEADER")
        payload = shape[0] * shape[1] * dtype.itemsize
        if stream.tell() + payload != size:
            raise ValueError("INDEX_NPY_SIZE")
        stream.seek(0)
        return np.load(stream, allow_pickle=False)
