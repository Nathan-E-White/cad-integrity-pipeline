"""Small local CLI. No inference endpoints, credentials, Gradio server, or import-time I/O."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .errors import IntegrityError
from .fixtures import cracked_cube
from .pipeline import RepairPipeline, RepairPolicy
from .repair import WeldPolicy
from .serialization import dumps


def _write_or_print(text: str, path: Path | None) -> None:
    if path is None:
        print(text)
    else:
        # Refuse overwriting existing evidence. For the native workflow the report is
        # a separate artifact, not a transactionally coupled STEP+JSON pair.
        with path.open("x", encoding="utf-8") as stream:
            stream.write(text + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local topology/CAD diagnostics; not certification")
    parser.add_argument("--verbose", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Repair a synthetic cracked cube; offline, no kernel needed")
    demo.add_argument("--report", type=Path)
    audit = commands.add_parser("audit-step", help="Audit a local STEP using OCP; does not edit it")
    audit.add_argument("input", type=Path)
    audit.add_argument("--report", type=Path)
    audit.add_argument("--max-tolerance-mm", type=float, default=1e-3)
    audit.add_argument("--expected-solids", type=int, default=1)
    heal = commands.add_parser("repair-step", help="Repair a private native copy and round-trip-check export")
    heal.add_argument("input", type=Path)
    heal.add_argument("output", type=Path)
    heal.add_argument("--report", type=Path, required=True)
    heal.add_argument("--precision-mm", type=float, default=1e-6)
    heal.add_argument("--max-tolerance-mm", type=float, default=1e-3)
    heal.add_argument("--expected-solids", type=int, default=1)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)
    try:
        if args.report is not None:
            if args.report.exists():
                raise FileExistsError(args.report)
            if not args.report.parent.is_dir():
                raise FileNotFoundError(args.report.parent)
        if args.command == "demo":
            result = RepairPipeline(RepairPolicy(weld=WeldPolicy(0.005, 0.005))).run(cracked_cube())
            _write_or_print(dumps(result.report), args.report)
            return 0 if result.report.decision == "topology_checks_passed" else 2
        from .adapters.ocp import KernelPolicy, audit_shape, read_step, run_step_pipeline
        policy = KernelPolicy(precision_mm=getattr(args, "precision_mm", 1e-6),
                              maximum_tolerance_mm=args.max_tolerance_mm,
                              expected_solids=args.expected_solids)
        if args.command == "audit-step":
            document = read_step(args.input, max_bytes=policy.max_input_bytes)
            report = audit_shape(document.shape, policy)
            _write_or_print(dumps({"source_sha256": document.source_sha256, "policy": policy,
                                   "normalized_unit": document.length_unit, "audit": report}), args.report)
            return 0 if report.accepted_under_policy else 2
        if args.report.resolve() in {args.input.resolve(), args.output.resolve()}:
            raise ValueError("Report, source, and STEP output must have distinct paths")
        report_dict = run_step_pipeline(args.input, args.output, policy)
        _write_or_print(dumps(report_dict), args.report)
        return 0
    except (IntegrityError, ValueError, OSError) as exc:
        print(f"cad-integrity: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
