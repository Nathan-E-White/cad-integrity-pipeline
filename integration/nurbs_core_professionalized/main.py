#!/usr/bin/env python3
"""CLI and callable STL -> features -> primitives -> JSON/optional STEP pipeline.

Example (coordinates measured in millimetres):
    python main.py scan.stl --units mm --cards scan.json --step scan.step --seed 42

STL has no unit metadata. JSON-only runs may leave units unspecified; STEP may
not. Thresholds are always expressed in the ORIGINAL input coordinate system.
"""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from NURBSCoreEngine import (
    CADGeometryCardEngine,
    GeometryValidationError,
    OptionalDependencyError,
    RANSACPrimitiveClassifier,
    STEPExportError,
    STEPGeometryExportEngine,
    write_text_atomic,
)
from STLReader import PointCloudGeometryEstimator, STLReader

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    input_path: Path
    cards_path: Path
    step_path: Path | None = None
    units: str = "unspecified"
    neighbors: int = 15
    spatial_tol: float = 0.01
    normal_tol_deg: float = 3.0
    curvature_threshold: float = 0.05
    max_fit_rmse: float | None = None
    max_radius: float | None = None
    seed: int = 42
    workers: int = 1
    batch_size: int = 1024
    max_facets: int = 2_000_000
    max_primitives: int = 100
    overwrite: bool = False


@dataclass(frozen=True, slots=True)
class PublicationError:
    path: Path
    error_type: str
    message: str
    errno: int | None


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Computed geometry and publication evidence for this invocation.

    Output paths are requested destinations. Only ``published_paths`` records
    writes that returned successfully; a failing destination may still exist.
    """

    cards: dict[str, Any]
    input_vertices: int
    valid_feature_count: int
    primitive_count: int
    unassigned_count: int
    elapsed_seconds: float
    cards_path: Path
    step_path: Path | None
    published_paths: tuple[Path, ...]
    publication_error: PublicationError | None

    @property
    def complete(self) -> bool:
        return self.publication_error is None


def run_pipeline(config: PipelineConfig) -> PipelineResult:
    """Execute the reference pipeline without configuring application logging.

    Export contents are generated before publishing either output. Each file is
    published atomically, but JSON and STEP are NOT a two-file transaction. A
    publication OSError stops further writes and is reported in PipelineResult,
    along with confirmed outputs. Validation and export-generation errors raise.
    """
    started = time.perf_counter()
    source = Path(config.input_path)
    cards_path = Path(config.cards_path)
    step_path = Path(config.step_path) if config.step_path is not None else None
    paths = [source.resolve(), cards_path.resolve()]
    if step_path is not None:
        paths.append(step_path.resolve())
    if len(set(paths)) != len(paths):
        raise GeometryValidationError("input, JSON output, and STEP output must be distinct paths")
    for output in (cards_path, step_path):
        if output is not None:
            if not output.parent.is_dir():
                raise FileNotFoundError(f"output directory does not exist: {output.parent}")
            if output.exists() and not config.overwrite:
                raise FileExistsError(f"refusing to overwrite {output}; use --overwrite explicitly")
    if step_path is not None and config.units == "unspecified":
        raise GeometryValidationError("--units is required when exporting STEP")

    estimator = PointCloudGeometryEstimator(
        k_neighbors=config.neighbors, batch_size=config.batch_size, workers=config.workers,
        max_radius=config.max_radius, max_fit_rmse=config.max_fit_rmse,
    )
    segmenter = RANSACPrimitiveClassifier(
        spatial_tol=config.spatial_tol, normal_tol_deg=config.normal_tol_deg,
        planar_threshold=config.curvature_threshold, random_state=config.seed,
        max_primitives=config.max_primitives,
    )
    card_engine = CADGeometryCardEngine(precision=4, length_unit=config.units)
    mesh = STLReader.read(source, max_facets=config.max_facets)
    if len(mesh.points) < 6:
        raise GeometryValidationError(
            "at least six distinct vertices are needed for quadratic features"
        )
    features = estimator.estimate(mesh.points, reference_normals=mesh.vertex_normals())
    segmentation = segmenter.segment(mesh.points, features.normals, features.curvatures)
    cards = card_engine.compute_cards(segmentation.primitives, mesh.points)
    valid_count = int(np.count_nonzero(features.valid_mask))
    unassigned_count = len(segmentation.unassigned_indices)
    settings = asdict(config)
    settings = {
        key: str(value) if isinstance(value, Path) else value
        for key, value in settings.items()
    }
    cards["provenance"] = {
        "input_mesh": asdict(mesh.report), "pipeline_settings": settings,
        "valid_feature_count": valid_count, "unassigned_count": unassigned_count,
        "unassigned_fraction": unassigned_count / len(mesh.points),
        "index_space": "exactly deduplicated STLReader vertex order",
    }
    if not segmentation.primitives:
        LOGGER.warning(
            "No supported primitives found; inspect feature validity and unit-dependent tolerances",
        )
    # Resolve backend / geometry failures before writing JSON, but do not claim
    # transactionality across these two separately published files.
    step_text = STEPGeometryExportEngine().export(cards) if step_path is not None else None
    json_text = card_engine.to_json(cards)
    outputs = [(cards_path, json_text)]
    if step_path is not None and step_text is not None:
        outputs.append((step_path, step_text))
    published_paths: list[Path] = []
    publication_error = None
    for output_path, text in outputs:
        try:
            write_text_atomic(output_path, text, overwrite=config.overwrite)
        except OSError as exc:
            publication_error = PublicationError(
                output_path, type(exc).__name__, str(exc), exc.errno,
            )
            break
        published_paths.append(output_path)
    elapsed = time.perf_counter() - started
    LOGGER.info(
        "Processed in %.3fs: %d valid features, %d primitives, %d/%d unassigned vertices",
        elapsed, valid_count, len(segmentation.primitives), unassigned_count, len(mesh.points),
    )
    return PipelineResult(
        cards, len(mesh.points), valid_count, len(segmentation.primitives),
        unassigned_count, elapsed, cards_path, step_path,
        tuple(published_paths), publication_error,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Extract bounded plane/cylinder surface fragments from an STL "
            "(not a solid reconstruction)"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("input", type=Path, help="binary or ASCII STL")
    parser.add_argument("--cards", type=Path, help="JSON output; default: <input>.geometry.json")
    parser.add_argument("--step", type=Path, help="optional STEP output; requires the [step] extra")
    parser.add_argument(
        "--units", choices=("mm", "cm", "m", "in"), default="unspecified",
        help="input length units; mandatory for STEP",
    )
    parser.add_argument(
        "--neighbors", type=int, default=15,
        help="local neighbor count, including query point",
    )
    parser.add_argument(
        "--spatial-tol", type=float, default=0.01,
        help="RANSAC distance tolerance in input units",
    )
    parser.add_argument("--normal-tol-deg", type=float, default=3.0)
    parser.add_argument(
        "--curvature-threshold", type=float, default=0.05,
        help="planarity cutoff in inverse input units",
    )
    parser.add_argument(
        "--max-fit-rmse", type=float,
        help="reject local fits above this input-unit RMSE",
    )
    parser.add_argument("--max-radius", type=float, help="maximum neighbor radius in input units")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--workers", type=int, default=1,
        help="KD-tree query workers; -1 uses all available",
    )
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument("--max-facets", type=int, default=2_000_000)
    parser.add_argument("--max-primitives", type=int, default=100)
    parser.add_argument(
        "--overwrite", action="store_true",
        help="allow replacement of existing outputs",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    config = PipelineConfig(
        input_path=args.input,
        cards_path=args.cards or args.input.with_suffix(".geometry.json"),
        step_path=args.step, units=args.units, neighbors=args.neighbors,
        spatial_tol=args.spatial_tol, normal_tol_deg=args.normal_tol_deg,
        curvature_threshold=args.curvature_threshold, max_fit_rmse=args.max_fit_rmse,
        max_radius=args.max_radius, seed=args.seed, workers=args.workers,
        batch_size=args.batch_size, max_facets=args.max_facets,
        max_primitives=args.max_primitives, overwrite=args.overwrite,
    )
    try:
        result = run_pipeline(config)
    except (OSError, ValueError) as exc:
        LOGGER.error("%s", exc, exc_info=args.verbose)
        return 2
    except (OptionalDependencyError, STEPExportError) as exc:
        LOGGER.error("%s", exc, exc_info=args.verbose)
        return 3
    if result.cards_path in result.published_paths:
        LOGGER.info("JSON: %s", result.cards_path)
    if result.step_path is not None and result.step_path in result.published_paths:
        LOGGER.info("STEP: %s", result.step_path)
    if result.publication_error is not None:
        error = result.publication_error
        LOGGER.error("Publication failed: %s (%s): %s", error.path, error.error_type, error.message)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
