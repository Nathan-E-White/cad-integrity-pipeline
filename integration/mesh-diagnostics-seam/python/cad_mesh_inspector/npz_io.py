"""Bounded geometry-only NPZ input for authorized local files.

Header-first validation adapted from the preserved delivery's
python/mesh_diagnostics/io.py; see PROVENANCE.json. No archive extraction occurs.
"""
from dataclasses import dataclass
from math import prod
from pathlib import Path
from zipfile import ZipFile

import numpy as np

from .arrays import mesh_arrays


@dataclass(frozen=True)
class ArchiveLimits:
    max_compressed_bytes: int = 64 * 1024 * 1024
    max_expanded_bytes: int = 128 * 1024 * 1024
    max_members: int = 4
    max_header_bytes: int = 10_000


def load_numeric_npz(path: str | Path, limits: ArchiveLimits = ArchiveLimits()) -> dict[str, np.ndarray]:
    """Return canonical, validated positions/triangles without changing source order.

    Invalid array content raises ValueError; malformed ZIP containers retain
    zipfile.BadZipFile. Units and identity belong to the caller's document.
    """
    if any(v <= 0 for v in vars(limits).values()):
        raise ValueError("Archive limits must be positive")
    allowed = {"positions.npy", "vertices.npy", "triangles.npy", "faces.npy"}
    with Path(path).open("rb") as handle:
        handle.seek(0, 2)
        if handle.tell() > limits.max_compressed_bytes:
            raise ValueError("NPZ compressed-byte budget exceeded")
        handle.seek(0)
        with ZipFile(handle) as archive:
            members = archive.infolist()
            names = [m.filename for m in members]
            if len(members) > limits.max_members or len(names) != len(set(names)):
                raise ValueError("Too many or duplicate NPZ members")
            if any(n not in allowed for n in names):
                raise ValueError("Unexpected NPZ member")
            if sum(m.file_size for m in members) > limits.max_expanded_bytes:
                raise ValueError("NPZ expanded-byte budget exceeded")
            for member in members:
                if member.flag_bits & 1:
                    raise ValueError("Encrypted NPZ members are unsupported")
                with archive.open(member) as stream:
                    version = np.lib.format.read_magic(stream)
                    reader = {(1, 0): np.lib.format.read_array_header_1_0,
                              (2, 0): np.lib.format.read_array_header_2_0}.get(version)
                    if reader is None:
                        raise ValueError("Unsupported NPY version")
                    shape, _, dtype = reader(stream, max_header_size=limits.max_header_bytes)
                    if dtype.hasobject or dtype.fields is not None or dtype.kind not in "fiu":
                        raise ValueError("NPZ arrays must be primitive numeric arrays")
                    size = prod(shape) * dtype.itemsize
                    if any(n < 0 for n in shape) or size > limits.max_expanded_bytes or size != member.file_size - stream.tell():
                        raise ValueError("Invalid NPY header shape or byte count")
            positions = set(names) & {"positions.npy", "vertices.npy"}
            triangles = set(names) & {"triangles.npy", "faces.npy"}
            if len(positions) != 1 or len(triangles) != 1:
                raise ValueError("Expected exactly one positions alias and exactly one triangles alias")
        handle.seek(0)
        with np.load(handle, allow_pickle=False, max_header_size=limits.max_header_bytes) as data:
            v, f = mesh_arrays(data[next(iter(positions))[:-4]], data[next(iter(triangles))[:-4]])
    return {"positions": v, "triangles": f}
