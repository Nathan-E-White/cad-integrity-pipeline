"""Bounded, pickle-free local NPZ reading. Local paths are trusted-server inputs.

Use upload/session authorization before calling this function. It is not an
arbitrary-path endpoint and does not accept URLs or extract ZIP members to disk.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from math import prod
from zipfile import ZipFile, BadZipFile
import numpy as np
from .model import MeshValidationError, TriangleMesh
from .legacy import mesh_from_mapping


@dataclass(frozen=True, slots=True)
class ArchiveLimits:
    max_compressed_bytes: int = 64 * 1024 * 1024
    max_expanded_bytes: int = 128 * 1024 * 1024
    max_members: int = 32
    max_header_bytes: int = 10_000


ALLOWED_MEMBERS = {f"{name}.npy" for name in (
    "vertices", "positions", "faces", "indices", "triangles", "reference_normals",
    "error_edges", "failed_face_ids", "triangle_parent_faces")}


def load_npz_arrays(path: str | Path, limits: ArchiveLimits = ArchiveLimits()) -> dict[str, np.ndarray]:
    """Read only primitive numerical NPY arrays; refuse object metadata/pickle.

    Inspect actual NPY headers and advertised shapes before NumPy allocates.
    A ZIP size check alone would not catch an NPY header claiming a huge array.
    Keep human/structured metadata in JSON outside NPZ or use a prepared payload.
    """
    try:
        with Path(path).open("rb") as handle:
            handle.seek(0, 2)
            if handle.tell() > limits.max_compressed_bytes:
                raise MeshValidationError("NPZ exceeds compressed-byte budget")
            handle.seek(0)
            with ZipFile(handle) as archive:
                members = archive.infolist()
                names = [m.filename for m in members]
                if len(members) > limits.max_members or len(names) != len(set(names)):
                    raise MeshValidationError("too many or duplicate NPZ members")
                if not members or any(n not in ALLOWED_MEMBERS for n in names):
                    raise MeshValidationError("unsupported NPZ member; only documented primitive arrays are accepted")
                if sum(m.file_size for m in members) > limits.max_expanded_bytes:
                    raise MeshValidationError("NPZ exceeds expanded-byte budget")
                for member in members:
                    if member.flag_bits & 1:
                        raise MeshValidationError("encrypted NPZ entries are unsupported")
                    with archive.open(member) as stream:
                        version = np.lib.format.read_magic(stream)
                        reader = {(1, 0): np.lib.format.read_array_header_1_0,
                                  (2, 0): np.lib.format.read_array_header_2_0}.get(version)
                        if reader is None:
                            raise MeshValidationError("only NPY format versions 1 and 2 are supported")
                        shape, _, dtype = reader(stream, max_header_size=limits.max_header_bytes)
                        if dtype.hasobject or dtype.fields is not None or dtype.kind not in "fiu":
                            raise MeshValidationError("NPZ must not contain pickled, structured, or nonnumeric arrays")
                        byte_count = prod(shape) * dtype.itemsize
                        if byte_count > limits.max_expanded_bytes or byte_count != member.file_size - stream.tell():
                            raise MeshValidationError("NPY shape/byte count is invalid or exceeds budget")
            handle.seek(0)
            with np.load(handle, allow_pickle=False, max_header_size=limits.max_header_bytes) as arrays:
                return {name: arrays[name] for name in arrays.files}
    except MeshValidationError:
        raise
    except (OSError, ValueError, EOFError, BadZipFile) as exc:
        raise MeshValidationError(f"cannot read numeric NPZ: {exc}") from exc


def load_triangle_mesh(path: str | Path, **metadata) -> TriangleMesh:
    """Geometry-only loader. Use load_npz_arrays when optional diagnostics are needed."""
    return mesh_from_mapping(load_npz_arrays(path), **metadata)
