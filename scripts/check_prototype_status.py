"""Enforce prototype lifecycle state and production import boundaries."""

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
IMPORT_PATTERN = re.compile(r"(?:\bfrom\s*|\bimport\s*(?:\(|))['\"](?P<path>\.{1,2}/[^'\"]+)['\"]")


class PrototypeEntry(NamedTuple):
    path: PurePosixPath
    status: str


def load_manifest(path: Path) -> dict[str, PrototypeEntry]:
    """Load and validate the repository-owned prototype lifecycle manifest."""
    data = tomllib.loads(path.read_text())
    if data.get("version") != 1:
        raise ValueError(f"{path}: version must be 1")
    raw_entries = data.get("prototype")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError(f"{path}: at least one [[prototype]] entry is required")

    entries: dict[str, PrototypeEntry] = {}
    for raw in raw_entries:
        if not isinstance(raw, dict):
            raise ValueError(f"{path}: each prototype entry must be a table")
        raw_path = raw.get("path")
        status = raw.get("status")
        if not isinstance(raw_path, str) or not raw_path:
            raise ValueError(f"{path}: prototype path must be a non-empty string")
        prototype_path = PurePosixPath(raw_path)
        if prototype_path.is_absolute() or ".." in prototype_path.parts:
            raise ValueError(f"{path}: prototype path must be repository-relative: {raw_path}")
        if status not in ALLOWED_STATES:
            raise ValueError(
                f"{path}: {raw_path} has invalid status {status!r}; "
                f"expected one of {sorted(ALLOWED_STATES)}"
            )
        normalized = prototype_path.as_posix()
        if normalized in entries:
            raise ValueError(f"{path}: duplicate prototype path: {normalized}")
        entries[normalized] = PrototypeEntry(prototype_path, status)
    return entries


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


def check_repository(
    repository: Path,
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    base: str,
    head: str | None = "HEAD",
) -> list[str]:
    """Return policy errors for prototype paths changed since ``base``."""
    manifest = repository / manifest_path
    entries = load_manifest(manifest)
    changed = _changed_paths(repository, base=base, head=head)
    errors: list[str] = []
    for changed_path in changed:
        for path, entry in entries.items():
            if changed_path != path and not changed_path.startswith(f"{path}/"):
                continue
            if entry.status == "active":
                break
            errors.append(
                f"{entry.status} prototype changed: {changed_path}; "
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
    """Resolve local imports reachable from production Svelte entrypoints."""
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
        for match in IMPORT_PATTERN.finditer(source.read_text()):
            imported = _resolve_import(source, match.group("path"))
            if imported is not None and imported not in visited:
                pending.append(imported)
    return {path.relative_to(repository_root) for path in visited}


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="Git base revision for the guarded diff")
    parser.add_argument("--head", default="HEAD", help="Git head revision; use WORKTREE locally")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repository = Path(_git(Path.cwd(), "rev-parse", "--show-toplevel"))
    head = None if args.head == "WORKTREE" else args.head
    try:
        errors = check_repository(
            repository,
            manifest_path=args.manifest,
            base=args.base,
            head=head,
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
