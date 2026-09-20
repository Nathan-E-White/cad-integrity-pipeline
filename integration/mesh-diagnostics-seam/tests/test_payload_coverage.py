"""Public-payload acceptance cases for LE-5 and LE-6."""
import numpy as np
import pytest

from cad_mesh_inspector import inspect_triangles

TRIANGLE = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
TETRA = [*TRIANGLE, [0, 0, 1]]
TETRA_FACES = [[0, 2, 1], [0, 1, 3], [1, 2, 3], [2, 0, 3]]


def inspect(vertices, faces, **policy):
    result = inspect_triangles(
        np.asarray(vertices, dtype=float).reshape(-1, 3),
        np.asarray(faces, dtype=int).reshape(-1, 3),
        mesh_id="fixture", revision="r1", frame_id="world", **policy,
    )
    return ({m.id: m for m in result.metrics}, {s.id: s for s in result.selections})


@pytest.mark.parametrize("vertices", [[], TRIANGLE], ids=["empty", "vertices-only"])
@pytest.mark.parametrize("require_closed", [False, True])
def test_empty_checks_are_unknown(vertices, require_closed):
    metrics, selections = inspect(vertices, [], require_closed=require_closed)
    for key in ("quality", "degenerate", "repeated", "duplicate", "nonmanifold", "winding"):
        assert metrics[key].status == "unknown"
        assert metrics[key].value == 0
        assert selections[key].face_ids == []
        assert selections[key].edge_pairs == []
    assert metrics["boundary"].status == ("unknown" if require_closed else "info")
    assert metrics["boundary"].value == 0
    assert metrics["minimum-quality"].status == "unknown"
    assert metrics["minimum-quality"].value is None
    assert metrics["scope"].status == "unknown"
    assert metrics["vertices"].status == metrics["triangles"].status == "info"
    assert metrics["vertices"].value == len(vertices)
    assert metrics["triangles"].value == 0


@pytest.mark.parametrize("vertices,faces,repeated_id", [
    (TRIANGLE, [[0, 0, 1]], 0),
    (TETRA, [*TETRA_FACES, [0, 0, 1]], 4),
])
@pytest.mark.parametrize("require_closed", [False, True])
def test_excluded_faces_make_zero_edge_counts_unknown(vertices, faces, repeated_id, require_closed):
    metrics, selections = inspect(vertices, faces, require_closed=require_closed)
    for key in ("nonmanifold", "winding"):
        assert metrics[key].status == "unknown"
        assert metrics[key].value == 0
        assert selections[key].edge_pairs == []
    assert metrics["boundary"].status == ("unknown" if require_closed else "info")
    assert metrics["boundary"].value == 0
    for key in ("repeated", "degenerate"):
        assert metrics[key].status == "fail"
        assert selections[key].face_ids == [repeated_id]
    assert metrics["duplicate"].status == "pass"


@pytest.mark.parametrize("require_closed", [False, True])
def test_detected_boundary_survives_partial_incidence(require_closed):
    metrics, selections = inspect(TRIANGLE, [[0, 1, 2], [0, 0, 1]], require_closed=require_closed)
    assert metrics["boundary"].status == ("fail" if require_closed else "info")
    assert metrics["boundary"].value == 3
    assert selections["boundary"].edge_pairs == [0, 1, 0, 2, 1, 2]


@pytest.mark.parametrize("key,faces", [
    ("winding", [[0, 1, 2], [0, 1, 3], [0, 0, 1]]),
    ("nonmanifold", [[0, 1, 2], [0, 1, 3], [1, 0, 4], [0, 0, 1]]),
])
def test_detected_edge_defects_survive_partial_incidence(key, faces):
    metrics, selections = inspect([*TETRA, [0, -1, 0]], faces)
    assert metrics[key].status == "fail"
    assert metrics[key].value == 1
    assert selections[key].edge_pairs == [0, 1]


@pytest.mark.parametrize("require_closed", [False, True])
@pytest.mark.parametrize("closed", [False, True])
def test_complete_incidence_controls(closed, require_closed):
    vertices, faces = (TETRA, TETRA_FACES) if closed else (TRIANGLE, [[0, 1, 2]])
    metrics, _ = inspect(vertices, faces, require_closed=require_closed)
    assert metrics["boundary"].status == (
        ("pass" if closed else "fail") if require_closed else "info"
    )
    assert metrics["boundary"].value == (0 if closed else 3)
    for key in ("nonmanifold", "winding", "quality", "degenerate", "repeated", "duplicate"):
        assert metrics[key].status == "pass"
    assert metrics["scope"].status == "unknown"


def test_duplicate_faces_remain_failures():
    metrics, selections = inspect(TRIANGLE, [[0, 1, 2], [0, 1, 2]])
    assert metrics["duplicate"].status == "fail"
    assert metrics["duplicate"].value == 2
    assert selections["duplicate"].face_ids == [0, 1]


def test_collinear_distinct_indices_do_not_make_incidence_partial():
    metrics, selections = inspect([[0, 0, 0], [1, 0, 0], [2, 0, 0]], [[0, 1, 2]])
    assert metrics["degenerate"].status == "fail"
    assert selections["degenerate"].face_ids == [0]
    for key in ("nonmanifold", "winding", "repeated"):
        assert metrics[key].status == "pass"


@pytest.mark.parametrize("vertices,faces,tolerance,expected_ids", [
    ([[0, 0, 0], [1, 0, 0], [2, 0, 0]], [[0, 1, 2]], 0, [0]),
    (TRIANGLE, [[0, 0, 1]], 0, [0]),
    (TRIANGLE, [[0, 1, 2]], 0.5, [0]),
    (TRIANGLE, [[0, 1, 2]], 0.49, []),
    (TRIANGLE, [[0, 1, 2]], 0, []),
], ids=["collinear", "repeated", "area-equality", "below-area-tolerance", "regular"])
def test_zero_threshold_still_selects_degeneracy(vertices, faces, tolerance, expected_ids):
    metrics, selections = inspect(vertices, faces, minimum_mean_ratio=0, area_tolerance=tolerance)
    for key in ("quality", "degenerate"):
        assert selections[key].face_ids == expected_ids
        assert metrics[key].value == len(expected_ids)
        assert metrics[key].status == ("fail" if expected_ids else "pass")
        assert metrics[key].selection_id == selections[key].id
    assert metrics["quality"].label == "Mean ratio below 0 or degenerate"
    assert selections["quality"].label == metrics["quality"].label


def test_positive_threshold_unions_faces_without_double_counting():
    vertices = [
        [0, 0, 0], [1, 0, 0], [2, 0, 0],
        [0, 0, 1], [1, 0, 1], [0, 0.01, 1],
        [0, 0, 2], [1, 0, 2], [0, 1, 2],
    ]
    metrics, selections = inspect(vertices, [[0, 1, 2], [3, 4, 5], [6, 7, 8]], minimum_mean_ratio=0.15)
    assert selections["quality"].face_ids == [0, 1]
    assert selections["degenerate"].face_ids == [0]
    assert metrics["quality"].value == 2
    assert metrics["degenerate"].value == 1
    assert metrics["quality"].status == metrics["degenerate"].status == "fail"
    assert metrics["quality"].label == "Mean ratio below 0.15 or degenerate"
    assert selections["quality"].label == metrics["quality"].label
    assert metrics["quality"].selection_id == selections["quality"].id


@pytest.mark.parametrize("threshold", [0, 0.15])
def test_empty_quality_union_is_unknown(threshold):
    metrics, selections = inspect([], [], minimum_mean_ratio=threshold)
    assert selections["quality"].face_ids == []
    assert metrics["quality"].value == 0
    assert metrics["quality"].status == "unknown"
    assert metrics["quality"].selection_id == selections["quality"].id
    assert metrics["quality"].label == f"Mean ratio below {threshold:g} or degenerate"
