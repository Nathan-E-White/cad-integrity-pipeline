"""Exhaustive and high-precision oracles for the public locator interface."""

import importlib.util
import sys
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np

from cad_integrity.models import PolyhedralBRep
from cad_integrity.surface import prepare_surface
from cad_integrity.uv import LocationPolicy, LocationStatus, prepare_locator


def grid(side):
    vertices = np.array(
        [[x, y, 0.05 * x * y] for y in range(side) for x in range(side)], dtype=float
    )
    faces = [
        [y * side + x, y * side + x + 1, (y + 1) * side + x + 1, (y + 1) * side + x]
        for y in range(side - 1)
        for x in range(side - 1)
    ]
    return vertices, faces


def test_all_candidates_match_exhaustive_numpy_and_legacy_sampling():
    root = Path(__file__).resolve().parents[1] / "integration/mesh_healing_extension"
    saved = {name: sys.modules.get(name) for name in ("mesh_healing_engine", "mesh_export")}
    try:
        modules = {}
        for name in saved:
            spec = importlib.util.spec_from_file_location(name, root / f"{name}.py")
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            modules[name] = module
        vertices, faces = grid(15)
        coordinates = dict(enumerate(vertices[:, :2]))
        surface = prepare_surface(PolyhedralBRep.from_polygons(vertices, faces))
        locator = prepare_locator(surface.qualify_chart(coordinates).admitted)
        legacy = modules["mesh_export"].UVSurfaceMap(
            modules["mesh_healing_engine"].MeshHealingEngine(vertices, faces), coordinates
        )
        queries = np.vstack(
            [
                np.random.default_rng(42).uniform(-1, 15, (120, 2)),
                vertices[:, :2],
                [[0.5, 0.5], [-0.5e-9, 0.5], [-2e-9, 0.5]],
            ]
        )
        result = locator.locate(queries)
        inside = []
        for i, query in enumerate(queries):
            pairs = np.einsum("ti,tij->tj", query - legacy.origins, legacy.inverse_edges)
            bc = np.column_stack((1 - pairs.sum(axis=1), pairs))
            candidates = np.flatnonzero(
                np.all(bc >= -1e-9, axis=1) & np.all(bc <= 1 + 1e-9, axis=1)
            )
            start, end = result.offsets[i : i + 2]
            np.testing.assert_array_equal(result.triangles[start:end], candidates)
            if len(candidates):
                np.testing.assert_allclose(
                    result.barycentric[start:end], bc[candidates], atol=2e-14
                )
                np.testing.assert_array_equal(
                    result.source_faces[start:end], legacy.parent_faces[candidates]
                )
                inside.append(query)
            else:
                assert result.records[i].status == LocationStatus.OUTSIDE
        np.testing.assert_allclose(locator.sample(inside), legacy.sample(inside), atol=3e-14)
        # This bounds actual tested work, not a wall-clock performance promise.
        assert result.usage.work_steps < len(queries) * len(legacy.triangles)
    finally:
        for name, previous in saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def test_high_precision_tolerance_oracle_for_translated_skew_triangles():
    with localcontext() as context:
        context.prec = 100
        for scale in (1e-50, 1.0, 1e50):
            uv = np.array([[0.2, -0.3], [1.7, 0.4], [0.6, 1.8]]) * scale
            surface = prepare_surface(
                PolyhedralBRep.from_polygons([[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 1, 2]])
            )
            tolerance = 1e-7
            locator = prepare_locator(
                surface.qualify_chart(dict(enumerate(uv))).admitted,
                policy=LocationPolicy(barycentric_tolerance=tolerance),
            )
            weights = np.array(
                [
                    [0.2, 0.3, 0.5],
                    [-0.5e-7, 0.5, 0.5 + 0.5e-7],
                    [-2e-7, 0.5, 0.5 + 2e-7],
                    [1.0, 0.0, 0.0],
                ]
            )
            queries = weights @ uv
            result = locator.locate(queries)
            a, b, c = [[Decimal(float(x)) for x in p] for p in uv]
            det = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            for i, query in enumerate(queries):
                x, y = map(lambda x: Decimal(float(x)), query)
                u = ((x - a[0]) * (c[1] - a[1]) - (y - a[1]) * (c[0] - a[0])) / det
                v = ((b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0])) / det
                expected = [1 - u - v, u, v]
                accepted = all(-Decimal(tolerance) <= w <= 1 + Decimal(tolerance) for w in expected)
                assert (result.records[i].status == LocationStatus.UNIQUE) == accepted
                if accepted:
                    np.testing.assert_allclose(
                        result.barycentric[result.offsets[i]],
                        list(map(float, expected)),
                        atol=2e-15,
                    )
