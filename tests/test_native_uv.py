"""Owned chart location through the installed host interface."""

import numpy as np

from cad_integrity.models import PolyhedralBRep
from cad_integrity.surface import prepare_surface
from cad_integrity.uv import LocationStatus, prepare_locator


def chart(vertices=None, faces=None, uv=None):
    vertices = [[0, 0, 0], [1, 0, 0], [0, 1, 0]] if vertices is None else vertices
    faces = [[0, 1, 2]] if faces is None else faces
    surface = prepare_surface(PolyhedralBRep.from_polygons(vertices, faces))
    uv = {i: p[:2] for i, p in enumerate(vertices)} if uv is None else uv
    result = surface.qualify_chart(uv)
    assert result.admitted is not None
    return result.admitted


def test_installed_chart_location_and_sampling():
    locator = prepare_locator(chart())
    result = locator.locate([[0.25, 0.25], [5, 5], [0, 0]])
    assert [r.status for r in result.records] == [
        LocationStatus.UNIQUE,
        LocationStatus.OUTSIDE,
        LocationStatus.UNIQUE,
    ]
    assert result.records[1].resolved is None
    np.testing.assert_array_equal(result.offsets, [0, 1, 1, 2])
    np.testing.assert_allclose(locator.sample([[0.25, 0.25]]), [[0.25, 0.25, 0]])


def test_shared_diagonal_and_vertex_keep_all_candidates_and_source_identity():
    locator = prepare_locator(chart([[0, 0, 0], [1, 0, 0], [1, 1, 1], [0, 1, 0]], [[0, 1, 2, 3]]))
    result = locator.locate([[0.5, 0.5], [0, 0], [0.8, 0.2]])
    assert [r.status for r in result.records] == [LocationStatus.AGREEING] * 2 + [
        LocationStatus.UNIQUE
    ]
    np.testing.assert_array_equal(result.offsets, [0, 2, 4, 5])
    np.testing.assert_array_equal(result.source_faces, [0] * 5)
    np.testing.assert_allclose(result.records[0].resolved, [0.5, 0.5, 0.5])
    np.testing.assert_allclose(result.records[2].resolved, [0.8, 0.2, 0.2])


def test_overlaps_are_ambiguous_and_coincident_sheets_keep_provenance():
    import pytest

    from cad_integrity.surface import ParameterizationError

    for height, status in ((1.0, LocationStatus.AMBIGUOUS), (0.0, LocationStatus.AGREEING)):
        vertices = [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, height], [1, 0, height], [0, 1, height]]
        locator = prepare_locator(chart(vertices, [[0, 1, 2], [3, 4, 5]]))
        result = locator.locate([[0.2, 0.3]])
        assert result.records[0].status == status
        np.testing.assert_array_equal(result.source_faces, [0, 1])
        if height:
            assert result.records[0].resolved is None
            with pytest.raises(ParameterizationError, match="ambiguous"):
                locator.sample([[0.2, 0.3]])
        else:
            np.testing.assert_allclose(locator.sample([[0.2, 0.3]]), [[0.2, 0.3, 0]])


def test_budget_stop_discards_incomplete_group_and_does_not_hide_conflict():
    import pytest

    from cad_integrity.errors import ResourceLimitExceeded
    from cad_integrity.uv import ExhaustedLimit, LocationLimits

    vertices = [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [0, 1, 1]]
    locator = prepare_locator(chart(vertices, [[0, 1, 2], [3, 4, 5]]))
    queries = [[100, 100], [0.2, 0.3], [100, 100]]
    limits = LocationLimits(max_candidates_per_query=1)
    result = locator.locate(queries, limits=limits)
    assert result.exhaustion.limit == ExhaustedLimit.CANDIDATES
    assert result.exhaustion.first_unfinished_query == 1
    assert [r.status for r in result.records] == [LocationStatus.OUTSIDE] + [
        LocationStatus.BUDGET_EXCEEDED
    ] * 2
    assert not len(result.xyz)
    np.testing.assert_array_equal(result.offsets, [0, 0, 0, 0])
    with pytest.raises(ResourceLimitExceeded, match="query 1"):
        locator.sample(queries, limits=limits)


def test_all_budget_classes_and_committed_prefix():
    import pytest

    from cad_integrity.errors import ResourceLimitExceeded
    from cad_integrity.uv import ExhaustedLimit, LocationLimits

    admitted = chart()
    for name in ("max_input_bytes", "max_owned_bytes", "max_work_steps", "max_output_bytes"):
        with pytest.raises(ResourceLimitExceeded):
            prepare_locator(admitted, limits=LocationLimits(**{name: 0}))
    locator = prepare_locator(admitted)
    for name in ("max_input_bytes", "max_owned_bytes", "max_output_bytes"):
        with pytest.raises(ResourceLimitExceeded):
            locator.locate([[0.2, 0.2]], limits=LocationLimits(**{name: 0}))
    stopped = locator.locate([[0.2, 0.2]], limits=LocationLimits(max_work_steps=0))
    assert stopped.exhaustion.limit == ExhaustedLimit.WORK
    # Budget permits one complete candidate group, but not the next group's output.
    complete = locator.locate([[0.2, 0.2], [0.3, 0.3]])
    stopped = locator.locate(
        [[0.2, 0.2], [0.3, 0.3]],
        limits=LocationLimits(max_output_bytes=complete.usage.output_bytes - 64),
    )
    assert stopped.records[0].status == LocationStatus.UNIQUE
    assert stopped.records[1].status == LocationStatus.BUDGET_EXCEEDED
    assert stopped.exhaustion.limit == ExhaustedLimit.OUTPUT
    np.testing.assert_array_equal(stopped.offsets, [0, 1, 1])
    assert stopped.usage.output_bytes <= complete.usage.output_bytes - 64
    # Mandatory metadata fits; traversal workspace does not.
    empty_candidates = locator.locate([[100, 100]])
    stopped = locator.locate(
        [[0.2, 0.2]], limits=LocationLimits(max_owned_bytes=empty_candidates.usage.output_bytes)
    )
    assert stopped.exhaustion.limit == ExhaustedLimit.STORAGE


def test_ownership_results_lifetime_immutable_exports_and_authoritative_handle():
    import gc

    import pytest

    from cad_integrity.surface import AdmittedChart

    admitted = chart()
    unrelated = chart([[0, 0, 7], [1, 0, 7], [0, 1, 7]])
    wrapped = AdmittedChart(unrelated.surface, admitted._handle)
    locator = prepare_locator(wrapped)
    queries = np.array([[0.2, 0.3]])
    result = locator.locate(queries)
    queries[:] = 100
    export = result._handle.arrays()
    export["xyz"][:] = 900
    np.testing.assert_allclose(locator.sample([[0.2, 0.3]]), [[0.2, 0.3, 0]])
    del locator, admitted, wrapped, unrelated
    gc.collect()
    np.testing.assert_allclose(result.xyz, [[0.2, 0.3, 0]])
    for array in (result.xyz, result.offsets, result.triangles, result.barycentric):
        with pytest.raises(ValueError):
            array.flags.writeable = True


def test_native_layout_alignment_and_nonforgeable_chart():
    import pytest

    from cad_integrity import _native
    from cad_integrity.uv import LocationLimits

    with pytest.raises(TypeError):
        _native.AdmittedChart()
    locator = prepare_locator(chart())
    limits = LocationLimits()._native_limits()
    bad = [
        np.zeros((2, 2), np.float32),
        np.zeros((2, 2), dtype=">f8"),
        np.zeros((2, 4))[:, ::2],
        np.zeros((3, 3)),
        np.zeros(2),
    ]
    for queries in bad:
        with pytest.raises(ValueError):
            locator._handle.locate(queries, limits)
    queries = np.ndarray((1, 2), dtype=np.float64, buffer=bytearray(17), offset=1)
    queries[:] = [0.2, 0.3]
    result = locator._handle.locate(queries, limits).arrays()
    np.testing.assert_allclose(result["resolved"], [[0.2, 0.3, 0]])


def test_empty_batch_invalid_later_input_and_policy_validation():
    import pytest

    from cad_integrity.errors import InvalidGeometry
    from cad_integrity.uv import LocationLimits, LocationPolicy

    locator = prepare_locator(chart())
    result = locator.locate(np.empty((0, 2)))
    assert result.records == ()
    np.testing.assert_array_equal(result.offsets, [0])
    assert locator.sample(np.empty((0, 2))).shape == (0, 3)
    with pytest.raises(InvalidGeometry):
        locator.locate([[0.2, 0.2], [np.nan, 0]])
    with pytest.raises(InvalidGeometry, match="outside"):
        locator.sample([[10, 10]])
    for value in (-1.0, np.nan, np.inf):
        with pytest.raises(ValueError):
            LocationPolicy(barycentric_tolerance=value)
    for value in (-1, True, 1 << 64, 2.5):
        with pytest.raises(ValueError):
            LocationLimits(max_work_steps=value)


def test_extreme_scales_translations_and_tolerance_envelopes():
    from cad_integrity.uv import LocationPolicy

    for scale, shift in ((1.0, 0.0), (1e-100, 0.0), (1e100, 0.0), (1.0, 1e9)):
        vertices = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]) * scale
        uv = {i: p[:2] + shift for i, p in enumerate(vertices)}
        locator = prepare_locator(
            chart(vertices, uv=uv), policy=LocationPolicy(barycentric_tolerance=1e-6)
        )
        query = np.array([[0.25, 0.25], [-0.5e-6, 0.5], [-2e-6, 0.5]]) * scale + shift
        result = locator.locate(query)
        assert [r.status for r in result.records] == [
            LocationStatus.UNIQUE,
            LocationStatus.UNIQUE,
            LocationStatus.OUTSIDE,
        ]
        np.testing.assert_allclose(
            np.array(result.records[0].resolved) / scale, [0.25, 0.25, 0], atol=1e-7
        )


def test_orientation_source_selection_and_concave_polygon():
    from cad_integrity.surface import ChartPolicy

    raw = PolyhedralBRep.from_polygons(
        [[0, 0, 0], [2, 0, 0], [1, 0.5, 0], [0, 2, 0], [10, 0, 0], [11, 0, 0], [10, 1, 0]],
        [[4, 5, 6], [0, 1, 2, 3]],
    )
    surface = prepare_surface(raw, face_ids=[1])
    uv = {i: [p[1], p[0]] for i, p in enumerate(raw.vertices) if i < 4}
    admitted = surface.qualify_chart(uv, policy=ChartPolicy(-1)).admitted
    result = prepare_locator(admitted).locate([[0.1, 0.3], [1.5, 1.5]])
    assert result.records[0].status == LocationStatus.UNIQUE
    assert result.source_faces[0] == 1
    assert result.records[1].status == LocationStatus.OUTSIDE


def test_concurrent_readonly_calls_and_old_chart_retention():
    from concurrent.futures import ThreadPoolExecutor

    surface = chart().surface
    old = prepare_locator(surface.qualify_chart({0: [0, 0], 1: [1, 0], 2: [0, 1]}).admitted)
    new = prepare_locator(surface.qualify_chart({0: [10, 10], 1: [11, 10], 2: [10, 11]}).admitted)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: old.sample([[0.2, 0.3]]), range(20)))
    for result in results:
        np.testing.assert_allclose(result, [[0.2, 0.3, 0]])
    assert new.locate([[0.2, 0.3]]).records[0].status == LocationStatus.OUTSIDE


def test_agreement_is_relative_to_canonical_first_candidate():
    vertices = [[x, y, z] for z in (0.0, 7.5e-9, -7.5e-9) for x, y in ((0, 0), (1, 0), (0, 1))]
    result = prepare_locator(chart(vertices, [[0, 1, 2], [3, 4, 5], [6, 7, 8]])).locate(
        [[0.2, 0.3]]
    )
    assert result.records[0].status == LocationStatus.AGREEING
    np.testing.assert_array_equal(result.triangles, [0, 1, 2])
    np.testing.assert_allclose(result.records[0].resolved, [0.2, 0.3, 0])
    assert np.isclose(result.records[0].maximum_discrepancy, 7.5e-9)


def test_ill_conditioned_chart_uses_safe_fallback_and_numerical_failure_is_typed():
    import pytest

    from cad_integrity.surface import ChartPolicy

    surface = chart().surface
    admitted = surface.qualify_chart(
        {0: [0, 0], 1: [1, 1], 2: [1, 1 + 1e-14]}, policy=ChartPolicy(relative_tolerance=0)
    ).admitted
    locator = prepare_locator(admitted)
    assert locator.locate([[0, 0]]).records[0].status == LocationStatus.UNIQUE
    # The inverse-conditioned envelope cannot safely prune this query. Failure of
    # the barycentric arithmetic is not falsely returned as an outside result.
    with pytest.raises(OverflowError, match="numerical range"):
        locator.locate([[1e308, -1e308]])


def test_output_stop_mid_group_keeps_only_complete_prefix():
    import pytest

    from cad_integrity.errors import ResourceLimitExceeded
    from cad_integrity.uv import ExhaustedLimit, LocationLimits

    vertices = [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [0, 1, 1]]
    locator = prepare_locator(chart(vertices, [[0, 1, 2], [3, 4, 5]]))
    queries = [[100, 100], [0.2, 0.3], [100, 100]]
    complete = locator.locate(queries)
    limits = LocationLimits(max_output_bytes=complete.usage.output_bytes - 64)
    result = locator.locate(queries, limits=limits)
    assert result.exhaustion.limit == ExhaustedLimit.OUTPUT
    assert result.exhaustion.first_unfinished_query == 1
    assert [r.status for r in result.records] == [LocationStatus.OUTSIDE] + [
        LocationStatus.BUDGET_EXCEEDED
    ] * 2
    np.testing.assert_array_equal(result.offsets, [0, 0, 0, 0])
    assert len(result.triangles) == 0
    with pytest.raises(ResourceLimitExceeded, match="OUTPUT"):
        locator.sample(queries, limits=limits)


def test_index_owned_limit_accounts_for_construction_workspace():
    import pytest

    from cad_integrity.errors import ResourceLimitExceeded
    from cad_integrity.uv import LocationLimits

    admitted = chart()
    locator = prepare_locator(admitted)
    assert locator.usage.owned_bytes > locator.usage.output_bytes
    with pytest.raises(ResourceLimitExceeded):
        prepare_locator(admitted, limits=LocationLimits(max_owned_bytes=locator.usage.output_bytes))
