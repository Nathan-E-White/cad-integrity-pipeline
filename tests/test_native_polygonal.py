"""Owned polygonal binding contracts, independent of host implementation details."""

import numpy as np

from cad_integrity import _native
from cad_integrity.fixtures import disk


def assess(raw=None, **limits):
    raw = disk() if raw is None else raw
    return _native.assess_polygonal(
        raw.vertices, raw.edges, raw.face_offsets, raw.face_coedges, raw.length_unit, **limits,
    )


def test_disk_binding_exports_admission_and_exact_signed_incidence():
    result = assess()
    assert result["admitted"]
    assert result["boundary_edge_ids"].tolist() == [0, 1, 2, 3]
    assert result["d1"][3].tolist() == [4, 4]
    assert result["d2"][3].tolist() == [4, 1]
    assert result["d2"][2].tolist() == [1, 1, 1, -1]


def test_binding_owns_inputs_and_independent_outputs():
    import gc

    raw = disk()
    vertices, edges = raw.vertices.copy(), raw.edges.copy()
    offsets, coedges = raw.face_offsets.copy(), raw.face_coedges.copy()
    result = _native.assess_polygonal(vertices, edges, offsets, coedges, "mm")
    vertices[:] = 0
    edges[:] = 0
    coedges[:] = 0
    del vertices, edges, offsets, coedges
    gc.collect()
    assert result["d2"][2].tolist() == [1, 1, 1, -1]
    result["edge_signs"][:] = 0
    result["d1"][2][:] = 0
    assert result["d2"][2].tolist() == [1, 1, 1, -1]
    assert assess()["d1"][2].tolist() == [-1, -1, 1, -1, 1, -1, 1, 1]


def test_float64_distinct_endpoints_do_not_collapse_through_float32():
    from dataclasses import replace

    raw = disk()
    xyz = raw.vertices.copy()
    xyz[0] = [1, 0, 0]
    xyz[1] = [1 + 2**-40, 0, 0]
    assert np.array_equal(xyz[0].astype(np.float32), xyz[1].astype(np.float32))
    result = assess(replace(raw, vertices=xyz))
    assert result["admitted"]
    assert result["collapsed_edge_ids"].size == 0


def test_exact_budget_limits_and_all_or_nothing_failure():
    import pytest

    result = assess()
    assert result["usage"]["input_bytes"] == 208
    assert result["usage"]["output_bytes"] == 480
    limits = {"max_" + key: value for key, value in result["usage"].items()}
    assert assess(**limits)["admitted"]
    for key in limits:
        with pytest.raises(_native.BudgetExceeded):
            assess(**(limits | {key: limits[key] - 1}))


def test_malformed_layout_references_and_arrays_fail_conversion():
    import pytest

    raw = disk()
    valid = [raw.vertices, raw.edges, raw.face_offsets, raw.face_coedges, "mm"]
    cases = [
        (0, raw.vertices.astype(np.float32)),
        (0, np.asfortranarray(raw.vertices)),
        (0, raw.vertices[:, :2]),
        (0, np.full((4, 3), np.nan)),
        (1, raw.edges.astype(np.int32)),
        (1, np.full((4, 2), -1, dtype=np.int64)),
        (1, np.full((4, 2), np.iinfo(np.int64).max, dtype=np.int64)),
        (2, np.array([0, -1, 4], dtype=np.int64)),
        (2, np.array([0, 3], dtype=np.int64)),
        (2, np.array([], dtype=np.int64)),
        (2, np.array([0, 2, 4], dtype=np.int64)),
        (3, np.array([0, 2, 3, -4], dtype=np.int64)),
        (3, np.array([np.iinfo(np.int64).min, 2, 3, -4], dtype=np.int64)),
        (3, np.array([np.iinfo(np.int64).max, 2, 3, -4], dtype=np.int64)),
        (3, np.arange(8, dtype=np.int64)[::2]),
        (3, np.array([1, 2, 3, -4], dtype=">i8")),
        (4, "furlong"),
    ]
    for index, invalid in cases:
        arguments = valid.copy()
        arguments[index] = invalid
        with pytest.raises(ValueError):
            _native.assess_polygonal(*arguments)


def test_diagnostics_survive_refusal_without_exposing_incidence():
    from dataclasses import replace

    raw = disk()
    invalid = replace(raw, face_coedges=np.array([1, -2, 3, -4], dtype=np.int64))
    result = assess(invalid)
    assert not result["admitted"]
    assert result["invalid_face_ids"].tolist() == [0]
    assert result["boundary_edge_ids"].tolist() == [0, 1, 2, 3]
    assert "d1" not in result and "d2" not in result
