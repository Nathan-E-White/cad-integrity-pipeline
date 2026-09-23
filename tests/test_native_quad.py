import numpy as np
import pytest

from cad_integrity.errors import InvalidGeometry, ResourceLimitExceeded
from cad_integrity.models import PolyhedralBRep
from cad_integrity.polygonal_cells import PolygonalLimits
from cad_integrity.quad import Reason, Seed, Stop, TraceLimits, prepare_quad_patch


def grid(n=5):
    return PolyhedralBRep.from_polygons(
        [(x, y, 0) for y in range(n) for x in range(n)],
        [(v, v+1, v+n+1, v+n) for y in range(n-1) for x in range(n-1)
         for v in [y*n+x]],
    )


def test_regular_grid_has_boundary_graph_and_no_canonical_launches():
    patch = prepare_quad_patch(grid())
    result = patch.trace()
    assert result.complete and result.canonical
    assert result.seeds == () and result.segments == ()
    assert len(patch.boundary_edges) == 16
    assert np.array_equal(patch.vertices[12], [2, 2, 0])


def edge(mesh, a, b):
    return next(i for i, ends in enumerate(mesh.edges) if set(ends) == {a, b})


def cube():
    return PolyhedralBRep.from_polygons(
        [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
         (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)],
        [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
         (2, 3, 7, 6), (0, 4, 7, 3), (1, 2, 6, 5)],
    )


def test_cube_launches_all_24_branches_and_records_12_half_step_encounters():
    patch = prepare_quad_patch(cube())
    result = patch.trace()
    assert result.canonical and result.complete
    assert len(result.seeds) == len(result.segments) == len(result.events) == 24
    assert {event.time2 for event in result.events} == {1}
    assert {event.reason for event in result.events} == {Reason.OPPOSING}
    assert all(segment.to_vertex == -1 for segment in result.segments)
    assert len({event.edge for event in result.events}) == 12
    assert result.segment_coordinates().shape == (24, 2, 3)


def test_ties_prefix_collision_and_seed_permutation():
    mesh = grid()
    patch = prepare_quad_patch(mesh)
    seeds = [Seed(10, 11, edge(mesh, 11, 12)), Seed(20, 7, edge(mesh, 7, 12)),
             Seed(30, 14, edge(mesh, 14, 13))]
    result = patch.trace(seeds)
    assert not result.canonical and result.complete
    assert result.events == patch.trace(seeds[::-1]).events
    assert result.segments == patch.trace(seeds[::-1]).segments
    first = {e.seed: e.reason for e in result.events if e.time2 == 2}
    assert first == {10: Reason.RIGHT_HAND, 20: Reason.ADVANCE, 30: Reason.ADVANCE}
    hit = next(e for e in result.events if e.seed == 30 and e.time2 == 4)
    assert (hit.reason, hit.blocker, hit.deposited_time2) == (Reason.DEPOSITED_TRACK, 10, 2)
    assert not any(s.seed == 10 and s.start2 >= 2 for s in result.segments)


@pytest.mark.parametrize("count", [2, 3, 4])
def test_opposite_and_multiway_vertex_arrivals(count):
    mesh = grid()
    starts = [11, 13, 7, 17][:count]
    result = prepare_quad_patch(mesh).trace(
        [Seed(i, v, edge(mesh, v, 12)) for i, v in enumerate(starts)]
    )
    assert len(result.events) == count
    assert all(e.time2 == 2 for e in result.events)
    reason = Reason.OPPOSING if count == 2 else Reason.SIMULTANEOUS
    assert {e.reason for e in result.events} == {reason}


def test_orientation_reversal_changes_only_declared_right_hand_rule():
    mesh = grid()
    reversed_mesh = PolyhedralBRep.from_polygons(
        mesh.vertices, [mesh.face_vertices(f)[::-1] for f in range(mesh.face_count)]
    )
    result = prepare_quad_patch(reversed_mesh).trace([
        Seed(10, 11, edge(reversed_mesh, 11, 12)),
        Seed(20, 7, edge(reversed_mesh, 7, 12)),
    ])
    assert [(e.seed, e.reason) for e in result.events[:2]] == [
        (10, Reason.ADVANCE), (20, Reason.RIGHT_HAND),
    ]


def test_torus_return_is_self_collision_not_budget_or_a_claim_of_geometric_periodicity():
    n = 5
    points = [(float(x), float(y), 0) for y in range(n) for x in range(n)]
    faces = [(y*n+x, y*n+(x+1)%n, ((y+1)%n)*n+(x+1)%n, ((y+1)%n)*n+x)
             for y in range(n) for x in range(n)]
    mesh = PolyhedralBRep.from_polygons(points, faces)
    patch = prepare_quad_patch(mesh)
    assert patch.trace().segments == ()
    result = patch.trace([Seed(9, 0, edge(mesh, 0, 1))])
    assert len(result.segments) == 5
    assert result.events[-1].reason == Reason.SELF_COLLISION
    assert (result.events[-1].vertex, result.events[-1].time2,
            result.events[-1].deposited_time2) == (0, 10, 0)


@pytest.mark.parametrize("limit,stop", [
    ({"max_events": 23}, Stop.EVENT_BUDGET),
    ({"max_segments": 23}, Stop.SEGMENT_BUDGET),
    ({"max_work_steps": 3200}, Stop.WORK_BUDGET),
    ({"max_output_bytes": 800}, Stop.OUTPUT_BUDGET),
])
def test_whole_simultaneous_batch_is_atomic(limit, stop):
    result = prepare_quad_patch(cube()).trace(limits=TraceLimits(**limit))
    assert result.stop == stop and not result.complete
    assert result.segments == result.events == ()
    assert len(result.unfinished) == 24
    assert result.last_committed_time2 is None


def test_budget_after_first_batch_retains_exact_prefix():
    mesh = grid()
    patch = prepare_quad_patch(mesh)
    seeds = [Seed(1, 11, edge(mesh, 11, 12)), Seed(2, 7, edge(mesh, 7, 12))]
    full = patch.trace(seeds)
    partial = patch.trace(seeds, limits=TraceLimits(max_events=2))
    assert partial.stop == Stop.EVENT_BUDGET
    assert partial.events == full.events[:2] and partial.segments == full.segments[:2]
    assert partial.last_committed_time2 == 2 and partial.unfinished == (2,)


def test_native_owner_and_result_lifetime_are_independent_of_input_aliases():
    mesh = cube()
    patch = prepare_quad_patch(mesh)
    expected = patch.trace()
    mesh.vertices.setflags(write=True)
    mesh.vertices[:] = 100
    del mesh
    result = patch.trace()
    del patch
    assert result.events == expected.events
    assert np.array_equal(result.segment_coordinates(), expected.segment_coordinates())
    with pytest.raises(ValueError):
        result.patch.vertices.setflags(write=True)
    with pytest.raises(ValueError):
        result.segment_coordinates().setflags(write=True)


def test_boundary_extraordinary_launch_and_corner_nonlaunch():
    original = grid()
    faces = [original.face_vertices(f) for f in range(original.face_count)
             if not (f % 4 >= 2 and f // 4 >= 2)]
    used = sorted(set(v for face in faces for v in face))
    lookup = {v: i for i, v in enumerate(used)}
    mesh = PolyhedralBRep.from_polygons(original.vertices[used],
                                      [[lookup[v] for v in face] for face in faces])
    patch = prepare_quad_patch(mesh)
    assert len(patch.canonical_seeds) == 4
    assert {s.vertex for s in patch.canonical_seeds} == {lookup[12]}
    assert patch.trace().complete


def test_oriented_relabelling_preserves_geometric_event_evidence():
    mesh = cube()
    order = [6, 2, 7, 1, 5, 3, 0, 4]
    inverse = {v: i for i, v in enumerate(order)}
    changed = PolyhedralBRep.from_polygons(
        mesh.vertices[order],
        [[inverse[v] for v in mesh.face_vertices(f)[1:] + mesh.face_vertices(f)[:1]]
         for f in reversed(range(mesh.face_count))],
    )
    def normalized(result):
        return sorted((tuple(a), tuple(b), s.start2, s.end2, e.reason)
                      for (a, b), s, e in zip(result.segment_coordinates(), result.segments,
                                             result.events, strict=True))
    assert normalized(prepare_quad_patch(mesh).trace()) == normalized(
        prepare_quad_patch(changed).trace()
    )


def test_admission_and_seed_failures_are_errors_not_partial_success():
    tri = PolyhedralBRep.from_polygons([[0, 0, 0], [1, 0, 0], [0, 1, 0]], [(0, 1, 2)])
    with pytest.raises(InvalidGeometry):
        prepare_quad_patch(tri)
    mesh = grid()
    patch = prepare_quad_patch(mesh)
    for seeds in ([Seed(1, 100, 0)], [Seed(-1, 0, 0)],
                  [Seed(1, 11, edge(mesh, 11, 12)), Seed(2, 11, edge(mesh, 11, 12))]):
        with pytest.raises(InvalidGeometry):
            patch.trace(seeds)
    for key in ("max_input_bytes", "max_owned_bytes", "max_work_steps", "max_output_bytes"):
        with pytest.raises(ResourceLimitExceeded):
            prepare_quad_patch(mesh, limits=PolygonalLimits(**{key: 0}))
    with pytest.raises(ResourceLimitExceeded):
        patch.trace([Seed(1, 11, edge(mesh, 11, 12))], limits=TraceLimits(max_owned_bytes=0))


def test_private_binding_rejects_dtype_layout_and_nonfinite_geometry():
    from cad_integrity import _native
    mesh = grid()
    args = [mesh.vertices, mesh.edges, mesh.face_offsets, mesh.face_coedges,
            "mm", 256_000_000, 512_000_000, 50_000_000, 256_000_000]
    for vertices in (mesh.vertices.astype(np.float32), mesh.vertices[::-1],
                     np.full_like(mesh.vertices, np.nan)):
        with pytest.raises(ValueError):
            _native.prepare_quad_patch(vertices, *args[1:])
    patch = prepare_quad_patch(mesh)
    limits = _native.QuadLimits(512_000_000, 50_000_000, 256_000_000, 1000, 1000)
    with pytest.raises(ValueError):
        patch._handle.trace(np.zeros((1, 3), dtype=np.float64), limits)


def test_stopped_future_track_cannot_block_another_particle():
    mesh = grid()
    result = prepare_quad_patch(mesh).trace([
        Seed(10, 11, edge(mesh, 11, 12)), Seed(20, 7, edge(mesh, 7, 12)),
        Seed(30, 23, edge(mesh, 23, 18)),
    ])
    # Seed 10 would have reached 13 at t=2, but stopped at 12 at t=1.
    crossing = next(e for e in result.events if e.seed == 30 and e.vertex == 13)
    assert crossing.reason == Reason.ADVANCE and crossing.time2 == 4
    assert [e for e in result.events if e.seed == 30][-1].reason == Reason.BOUNDARY


def test_coincident_components_do_not_collide_and_shared_launches_do_not_self_stop():
    mesh = grid()
    faces = [mesh.face_vertices(f) for f in range(mesh.face_count)]
    doubled = PolyhedralBRep.from_polygons(
        np.vstack((mesh.vertices, mesh.vertices)),
        faces + [tuple(v + 25 for v in face) for face in faces],
    )
    result = prepare_quad_patch(doubled).trace([
        Seed(1, 11, edge(doubled, 11, 12)), Seed(2, 32, edge(doubled, 32, 37)),
    ])
    assert [e.reason for e in result.events[:2]] == [Reason.ADVANCE, Reason.ADVANCE]
    result = prepare_quad_patch(mesh).trace([
        Seed(1, 12, edge(mesh, 12, 13)), Seed(2, 12, edge(mesh, 12, 17)),
    ])
    assert result.complete and len(result.segments) == 4
    assert {e.reason for e in result.events} == {Reason.ADVANCE, Reason.BOUNDARY}


def test_seeded_arrival_at_unlaunched_extraordinary_vertex_stops_explicitly():
    mesh = cube()
    result = prepare_quad_patch(mesh).trace([Seed(1, 0, edge(mesh, 0, 1))])
    assert result.complete and not result.canonical
    assert len(result.events) == 1 and result.events[0].reason == Reason.EXTRAORDINARY


def lattice_oracle(mesh, seeds, n):
    """Independent half-step particle simulation on an axis-aligned integer lattice.

    No native rotation, priority queue, edge scheduler or mesh admission helpers.
    Every head moves half an edge per tick; contact is checked at integer doubled
    coordinates. Output is only observable event endpoints, times and reasons.
    """
    heads, directions, previous_vertex, start_time = {}, {}, {}, {}
    deposited = {}
    for seed in seeds:
        x, y, _ = mesh.vertices[seed.vertex]
        other = next(v for v in mesh.edges[seed.edge] if v != seed.vertex)
        dx, dy, _ = mesh.vertices[other] - mesh.vertices[seed.vertex]
        heads[seed.id] = (int(2*x), int(2*y))
        directions[seed.id] = (int(dx), int(dy))
        previous_vertex[seed.id] = (int(2*x), int(2*y))
        start_time[seed.id] = 0
        deposited.setdefault(heads[seed.id], set()).add(seed.id)
    events = []
    for tick in range(1, 4*n+1):
        if not heads:
            return events
        arrivals = {}
        for sid, point in heads.items():
            dx, dy = directions[sid]
            point = (point[0]+dx, point[1]+dy)
            arrivals.setdefault(point, []).append(sid)
        new_heads = {}
        for point, participants in arrivals.items():
            at_vertex = point[0] % 2 == 0 and point[1] % 2 == 0
            for sid in participants:
                reason = Reason.ADVANCE
                if at_vertex and (point[0] in (0, 2*(n-1)) or point[1] in (0, 2*(n-1))):
                    reason = Reason.BOUNDARY
                elif point in deposited:
                    reason = Reason.SELF_COLLISION if sid in deposited[point] else Reason.DEPOSITED_TRACK
                elif len(participants) >= 3:
                    reason = Reason.SIMULTANEOUS
                elif len(participants) == 2:
                    other = next(i for i in participants if i != sid)
                    dx, dy = directions[sid]
                    ox, oy = directions[other]
                    if (dx, dy) == (-ox, -oy):
                        reason = Reason.OPPOSING
                    elif dx*oy - dy*ox > 0:
                        reason = Reason.RIGHT_HAND
                if at_vertex or reason != Reason.ADVANCE:
                    events.append((tick, sid, previous_vertex[sid], point,
                                   start_time[sid], reason))
                    previous_vertex[sid] = point
                    start_time[sid] = tick
                if reason == Reason.ADVANCE:
                    new_heads[sid] = point
        for point, participants in arrivals.items():
            deposited.setdefault(point, set()).update(participants)
        heads = new_heads
    raise AssertionError("Finite planar oracle failed to terminate")


def test_exhaustive_two_particle_lattice_oracle_and_every_event_budget_cut():
    from itertools import combinations
    mesh = grid()
    patch = prepare_quad_patch(mesh)
    launches = [(int(v), e) for e, ends in enumerate(mesh.edges) for v in ends]
    assert len(launches) == 80
    for first, second in combinations(launches, 2):
        seeds = [Seed(0, *first), Seed(1, *second)]
        expected = sorted(lattice_oracle(mesh, seeds, 5))
        result = patch.trace(seeds)
        coords = result.segment_coordinates()
        observed = [(e.time2, e.seed, tuple((2*a[:2]).astype(int)),
                     tuple((2*b[:2]).astype(int)), s.start2, e.reason)
                    for e, s, (a, b) in zip(result.events, result.segments, coords, strict=True)]
        assert observed == expected, seeds
        for limit in range(len(expected)+1):
            partial = patch.trace(seeds, limits=TraceLimits(max_events=limit))
            # A time group fits only if its entire cumulative event count fits.
            prefix = [event for event in expected
                      if sum(other[0] <= event[0] for other in expected) <= limit]
            assert [(e.time2, e.seed, e.reason) for e in partial.events] == [
                (e[0], e[1], e[5]) for e in prefix
            ], (seeds, limit)
            assert partial.complete == (len(prefix) == len(expected))


def test_quad_specific_shared_face_path_is_rejected_with_face_evidence():
    from cad_integrity.polygonal_cells import admit_polygonal_cells
    mesh = PolyhedralBRep.from_polygons(
        [(i, i*i, 0) for i in range(5)], [(0, 1, 2, 3), (2, 1, 0, 4)]
    )
    assert admit_polygonal_cells(mesh).cells is not None
    with pytest.raises(InvalidGeometry, match="face 1"):
        prepare_quad_patch(mesh)


def test_quad_specific_parallel_edge_is_rejected_with_edge_evidence():
    from cad_integrity.polygonal_cells import admit_polygonal_cells
    # A sphere made by gluing two hexagonal disks. The lower disk has a
    # different quadrangulation and its own distinct 0--3 interior edge.
    faces = [(0, 1, 2, 3), (3, 4, 5, 0)]
    for outer, inner in [((3, 2, 1, 0), (6, 7, 8, 9)),
                         ((0, 5, 4, 3), (10, 11, 12, 13))]:
        for i in range(4):
            j = (i+1) % 4
            faces.append((outer[i], outer[j], inner[j], inner[i]))
        faces.append(inner)
    raw = PolyhedralBRep.from_polygons([(i, i*i, 0) for i in range(14)], faces)
    shared = edge(raw, 0, 3)
    edges = np.vstack((raw.edges, raw.edges[shared]))
    coedges = raw.face_coedges.copy()
    for i in range(int(raw.face_offsets[2]), len(coedges)):
        if abs(coedges[i]) == shared+1:
            coedges[i] = len(edges) if coedges[i] > 0 else -len(edges)
    mesh = PolyhedralBRep(raw.vertices, edges, raw.face_offsets, coedges)
    assert admit_polygonal_cells(mesh).cells is not None
    with pytest.raises(InvalidGeometry, match=f"edge {len(edges)-1}"):
        prepare_quad_patch(mesh)
