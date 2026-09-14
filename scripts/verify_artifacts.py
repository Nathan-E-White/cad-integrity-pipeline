"""Regenerate or verify versioned artifact manifests."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_mapping(base: Path, manifest: Path, entries: dict[str, str]) -> list[str]:
    errors = []
    for relative, expected in sorted(entries.items()):
        candidate = base / relative
        if not candidate.is_file():
            errors.append(f"{manifest}: missing {relative}")
        elif digest(candidate) != expected:
            errors.append(f"{manifest}: digest mismatch for {relative}")
    return errors


def gencad_entries(payload: dict[str, object]) -> dict[str, str]:
    entries = {}
    for case in payload.get("cases", []):
        for asset in case["assets"]:
            entries[asset["local_path"]] = asset["sha256"]
    notice = payload["source_notice"]
    entries[notice["local_path"]] = notice["sha256"]
    return entries


def project_entries() -> dict[str, str]:
    ignored = {".git", ".idea", ".pixi", "__pycache__", ".pytest_cache", ".mypy_cache",
               ".ruff_cache", "build", "dist"}
    entries = {}
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if any(part in ignored for part in relative.parts) or not path.is_file():
            continue
        if relative.as_posix() == "SHA256SUMS.json":
            continue
        entries[relative.as_posix()] = digest(path)
    return dict(sorted(entries.items()))


def main() -> int:
    if sys.argv[1:] == ["--write"]:
        (ROOT / "SHA256SUMS.json").write_text(json.dumps(project_entries(), indent=2) + "\n")
    elif sys.argv[1:]:
        raise SystemExit("usage: verify_artifacts.py [--write]")

    package_manifest = ROOT / "SHA256SUMS.json"
    package_entries = json.loads(package_manifest.read_text())
    errors = verify_mapping(ROOT, package_manifest, package_entries)

    for relative in (
        "examples/gencad/manifest.json",
        "examples/pathological-mesh-fixtures/manifest.json",
    ):
        manifest = ROOT / relative
        payload = json.loads(manifest.read_text())
        if "cases" in payload:
            entries = gencad_entries(payload)
        else:
            entries = {entry["path"]: entry["sha256"] for entry in payload.get("files", [])}
        errors.extend(verify_mapping(manifest.parent, manifest, entries))
    if errors:
        print("\n".join(errors))
        return 1
    print("Artifact manifests verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
