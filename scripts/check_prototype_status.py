"""Enforce prototype lifecycle state and production build boundaries."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path, PurePosixPath
from typing import NamedTuple

ALLOWED_STATES = frozenset({"active", "read_only", "archived"})
DEFAULT_MANIFEST = Path("components/inspection_workspace/frontend/prototype-status.toml")
IMPORT_PATTERN = re.compile(
    r"(?:\bfrom\s*|\bimport\s*(?:\(|)|\bnew\s+URL\s*\()['\"]"
    r"(?P<path>\.{1,2}/[^'\"]+)['\"]"
)


class PrototypeEntry(NamedTuple):
    path: PurePosixPath
    status: str
    bundle_markers: tuple[str, ...]


def _parse_manifest(text: str, source: str) -> dict[str, PrototypeEntry]:
    data = tomllib.loads(text)
    if data.get("version") != 1:
        raise ValueError(f"{source}: version must be 1")
    raw_entries = data.get("prototype")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError(f"{source}: at least one [[prototype]] entry is required")

    entries: dict[str, PrototypeEntry] = {}
    for raw in raw_entries:
        if not isinstance(raw, dict):
            raise ValueError(f"{source}: each prototype entry must be a table")
        raw_path = raw.get("path")
        status = raw.get("status")
        raw_markers = raw.get("bundle_markers", [])
        if not isinstance(raw_path, str) or not raw_path:
            raise ValueError(f"{source}: prototype path must be a non-empty string")
        prototype_path = PurePosixPath(raw_path)
        if prototype_path.is_absolute() or ".." in prototype_path.parts:
            raise ValueError(f"{source}: prototype path must be repository-relative: {raw_path}")
        if status not in ALLOWED_STATES:
            raise ValueError(
                f"{source}: {raw_path} has invalid status {status!r}; "
                f"expected one of {sorted(ALLOWED_STATES)}"
            )
        if not isinstance(raw_markers, list) or not all(
            isinstance(marker, str) and marker for marker in raw_markers
        ):
            raise ValueError(f"{source}: {raw_path} bundle_markers must be strings")
        normalized = prototype_path.as_posix()
        if normalized in entries:
            raise ValueError(f"{source}: duplicate prototype path: {normalized}")
        entries[normalized] = PrototypeEntry(prototype_path, status, tuple(raw_markers))
    return entries


def load_manifest(path: Path) -> dict[str, PrototypeEntry]:
    """Load and validate the repository-owned prototype lifecycle manifest."""
    return _parse_manifest(path.read_text(), str(path))


def _git(repository: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _changed_paths(repository: Path, *, base: str, head: str | None) -> tuple[str, ...]:
    comparison = f"{base}...{head}" if head else base
    output = _git(
        repository,
        "diff",
        "--name-only",
        "--diff-filter=ACDMRTUXB",
        comparison,
    )
    return tuple(line for line in output.splitlines() if line)


def _manifest_at_revision(
    repository: Path, manifest_path: Path, revision: str
) -> dict[str, PrototypeEntry]:
    result = subprocess.run(
        ["git", "-C", str(repository), "show", f"{revision}:{manifest_path.as_posix()}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {}
    return _parse_manifest(result.stdout, f"{revision}:{manifest_path.as_posix()}")


def _effective_base(base: str, fallback_base: str | None) -> str:
    if base and set(base) == {"0"}:
        if fallback_base is None:
            raise ValueError("an all-zero push base requires --fallback-base")
        return fallback_base
    return base


def check_repository(
    repository: Path,
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    base: str,
    fallback_base: str | None = None,
    head: str | None = "HEAD",
) -> list[str]:
    """Return policy errors for prototype paths changed since ``base``."""
    base = _effective_base(base, fallback_base)
    head_entries = load_manifest(repository / manifest_path)
    base_entries = _manifest_at_revision(repository, manifest_path, base)
    changed = _changed_paths(repository, base=base, head=head)
    all_paths = sorted(set(base_entries) | set(head_entries), key=len, reverse=True)
    errors: list[str] = []
    for changed_path in changed:
        for path in all_paths:
            if changed_path != path and not changed_path.startswith(f"{path}/"):
                continue
            base_entry = base_entries.get(path)
            head_entry = head_entries.get(path)
            if head_entry is not None and head_entry.status == "active":
                break
            protected_entry = next(
                (
                    entry
                    for entry in (base_entry, head_entry)
                    if entry is not None and entry.status != "active"
                ),
                None,
            )
            if protected_entry is None:
                break
            errors.append(
                f"{protected_entry.status} prototype changed: {changed_path}; "
                f"promote {path} to active in {manifest_path.as_posix()} in the same change"
            )
            break
    return errors


def _resolve_import(source: Path, specifier: str) -> Path | None:
    candidate = (source.parent / specifier).resolve()
    possibilities = [
        candidate,
        candidate.with_suffix(".ts"),
        candidate.with_suffix(".svelte"),
        candidate.with_suffix(".js"),
        candidate / "index.ts",
        candidate / "index.svelte",
        candidate / "index.js",
    ]
    return next((path for path in possibilities if path.is_file()), None)


def production_import_graph(frontend: Path, *, entrypoints: tuple[Path, ...]) -> set[Path]:
    """Resolve local imports and URL assets reachable from production entrypoints."""
    frontend_root = frontend.resolve()
    repository_root = frontend_root.parents[2]
    pending = [(frontend_root / entrypoint).resolve() for entrypoint in entrypoints]
    visited: set[Path] = set()
    while pending:
        source = pending.pop()
        if source in visited:
            continue
        if not source.is_relative_to(repository_root):
            raise ValueError(f"production import escapes repository root: {source}")
        visited.add(source)
        try:
            content = source.read_text()
        except UnicodeDecodeError:
            continue
        for match in IMPORT_PATTERN.finditer(content):
            imported = _resolve_import(source, match.group("path"))
            if imported is not None and imported not in visited:
                pending.append(imported)
    return {path.relative_to(repository_root) for path in visited}


def production_boundary_errors(
    frontend: Path,
    *,
    entrypoints: tuple[Path, ...],
    bundle_root: Path,
    entries: dict[str, PrototypeEntry],
) -> list[str]:
    """Check production source closure and generated assets for prototype content."""
    repository_root = frontend.resolve().parents[2]
    errors: list[str] = []
    for imported in sorted(production_import_graph(frontend, entrypoints=entrypoints)):
        imported_path = imported.as_posix()
        for prototype_path in entries:
            if imported_path == prototype_path or imported_path.startswith(f"{prototype_path}/"):
                errors.append(f"production import reaches prototype path: {imported_path}")
                break
    if not bundle_root.is_dir():
        return errors + [f"generated bundle directory is missing: {bundle_root}"]
    for bundle in sorted(path for path in bundle_root.rglob("*") if path.is_file()):
        try:
            content = bundle.read_text()
        except UnicodeDecodeError:
            continue
        bundle_path = bundle.resolve().relative_to(repository_root).as_posix()
        for prototype_path, entry in entries.items():
            for marker in entry.bundle_markers:
                if marker in content:
                    errors.append(
                        f"generated bundle contains marker from {prototype_path}: "
                        f"{marker} ({bundle_path})"
                    )
    return errors


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="Git base revision for the guarded diff")
    parser.add_argument(
        "--fallback-base", help="Base used when --base is an all-zero new-branch SHA"
    )
    parser.add_argument("--head", default="HEAD", help="Git head revision; use WORKTREE locally")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--check-production-boundary",
        action="store_true",
        help="Check production entrypoint closure and generated component bundles",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repository = Path(_git(Path.cwd(), "rev-parse", "--show-toplevel"))
    head = None if args.head == "WORKTREE" else args.head
    try:
        if args.base is None and not args.check_production_boundary:
            raise ValueError("provide --base or --check-production-boundary")
        errors: list[str] = []
        if args.base is not None:
            errors.extend(
                check_repository(
                    repository,
                    manifest_path=args.manifest,
                    base=args.base,
                    fallback_base=args.fallback_base,
                    head=head,
                )
            )
        if args.check_production_boundary:
            entries = load_manifest(repository / args.manifest)
            frontend = repository / "components/inspection_workspace/frontend"
            errors.extend(
                production_boundary_errors(
                    frontend,
                    entrypoints=(Path("Index.svelte"), Path("Example.svelte")),
                    bundle_root=(
                        repository / "components/inspection_workspace/backend/"
                        "gradio_inspectionworkspace/templates"
                    ),
                    entries=entries,
                )
            )
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"prototype status check failed: {error}", file=sys.stderr)
        return 2
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("prototype status check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
