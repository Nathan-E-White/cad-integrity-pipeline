"""Generate the documented NPZ schema. Run from the project root. Requires NumPy."""
from pathlib import Path
import numpy as np

path = Path("public/example.npz")
path.parent.mkdir(parents=True, exist_ok=True)
# Keep original vertex ordering and unnormalized parametric coordinates.
positions = np.array([[0, 0, 0], [40, 0, 0], [40, 30, 8], [0, 30, 0]], dtype=np.float64)
triangles = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)
uv = np.array([[0, 0], [4, 0], [4, 3], [0, 3]], dtype=np.float64)
triangle_faces = np.array([101, 102], dtype=np.int32)
np.savez_compressed(path, positions=positions, triangles=triangles, uv=uv, triangle_faces=triangle_faces)
print(path)
