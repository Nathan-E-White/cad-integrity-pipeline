
import numpy as np
from typing import Dict, Any, List

def compute_motorcycle_paths(npz_fp: str) -> Dict[str, Any]:
    """
    Extracts mesh geometry and traces motorcycle graph trajectories.

    Expected NPZ structure:
      - vertices: (N, 3) matrix of coordinates
      - faces: (M, 3) triangle element indexing matrix
      - motorcycle_paths: Pickled/structured list of path dicts containing:
            {'id': int, 'coords': [[x1, y1, z1], [x2, y2, z2], ...], 'active': bool}
    """
    with np.load(npz_fp, allow_pickle=True) as data:
        # Core data
        v = data['vertices']
        f = data['faces']

        # Pull motorcycle lines out if they exist;
        # generate simulated placeholders otherwise
        if "motorcycle_paths" not in data:
            raw_paths = _gen_synthetic_mpaths(v)
        else:
            raw_paths = data['motorcycle_paths']

    processed_paths = []
    metrics_list = []

    total_traces = len(raw_paths)
    active_traces = 0
    crashed_traces = 0

    for path in raw_paths:
        coords = np.asarray(path['coords'], dtype=np.float32)
        if len(coords) < 2:
            continue

        # Reconstruct for 3.js
        segments = []
        for i in range(len(coords) - 1):
            segments.extend(coords[i].toList())
            segments.append(coords[i + 1].toList())

        is_active = path['active']
        if is_active:
            active_traces += 1
        else:
            crashed_traces += 1

        processed_paths.append({
            "id": int(path["id"]),
            "segments": segments,
            "status": "active" if is_active else "crashed",
            "length": float(np.sum(np.linalg.norm(np.diff(coords, axis=0), axis=1)))
        })

    # Structure industrial metrics for your Svelte sidebar panel layout
    metrics_list.append({
        "id": "all_paths",
        "label": "Total Singular Motorcycles",
        "value": total_traces,
        "status": "pass" if total_traces < 12 else "fail"
    })

    metrics_list.append({
        "id": "active_paths",
        "label": "Unbounded/Cyclical Loops",
        "value": active_traces,
        "status": "pass" if active_traces == 0 else "fail"
    })

    return {
        "vertices": v.astype(np.float32).ravel().tolist(),
        "faces": f.astype(np.float32).ravel().tolist(),
        "metrics": metrics_list,
    }


def _generate_synthetic_motorcycles(vertices: np.ndarray) -> List[Dict[str, Any]]:
    """ Fallback mock traces aligned over your 20kB mesh spatial domain. """
    bbox_min = np.min(vertices, axis=0)
    bbox_max = np.max(vertices, axis=0)
    center = (bbox_min + bbox_max) / 2.0
    span = np.linalg.norm(bbox_max - bbox_min)

    mock_paths = []
    # Generate a horizontal structural split path lines layout
    for i in range(4):
        offset = (i - 1.5) * (span * 0.1)
        coords = [
            [center[0] - span * 0.4, center[1] + offset, center[2] + span * 0.05],
            [center[0] - span * 0.1, center[1] + offset, center[2] + span * 0.05],
            [center[0] + span * 0.2 + (i * 0.02), center[1] + offset * (0.2 if i % 2 == 0 else 1.5),
             center[2] + span * 0.05]
        ]
        mock_paths.append({
            "id": 100 + i,
            "coords": coords,
            "active": True if i == 0 else False
        })
    return mock_paths