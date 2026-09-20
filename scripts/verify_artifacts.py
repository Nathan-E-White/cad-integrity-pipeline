"""Regenerate or verify versioned artifact manifests."""
from __future__ import annotations

import hashlib
import json
import subprocess
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
    """Inventory source files using Git's tracked and unignored file semantics.

    Untracked source is included so forgotten additions fail verification. Tracked
    files remain covered even if a later ignore rule matches them. Run in a Git
    checkout; never silently replace this inventory with a different filesystem scan.
    """
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE,
    )
    names = {name.decode("utf-8") for name in result.stdout.split(b"\0") if name}
    entries = {
        name: digest(ROOT / name) for name in names
        if name != "SHA256SUMS.json" and (ROOT / name).is_file()
    }
    return dict(sorted(entries.items()))


def bundle_entries(manifest: Path) -> dict[str, str]:
    """The bundle manifest declares its own inventory; archives stay immutable."""
    return {
        name.removeprefix("*"): expected
        for expected, name in (line.split(maxsplit=1) for line in manifest.read_text().splitlines()
                               if line.strip())
    }


def main() -> int:
    bundles = [ROOT / "integration" / name / "SHA256SUMS" for name in (
        "mesh_healing_extension", "nurbs_core_professionalized",
    )]
    if sys.argv[1:] == ["--write"]:
        for manifest in bundles:
            manifest.write_text("".join(
                f"{digest(manifest.parent / name)}  {name}\n"
                for name in bundle_entries(manifest)
            ))
        (ROOT / "SHA256SUMS.json").write_text(json.dumps(project_entries(), indent=2) + "\n")
    elif sys.argv[1:]:
        raise SystemExit("usage: verify_artifacts.py [--write]")

    package_manifest = ROOT / "SHA256SUMS.json"
    package_entries = json.loads(package_manifest.read_text())
    errors = verify_mapping(ROOT, package_manifest, package_entries)
    for manifest in bundles:
        errors.extend(verify_mapping(manifest.parent, manifest, bundle_entries(manifest)))
    expected_entries = project_entries()
    for relative in sorted(set(package_entries) - set(expected_entries)):
        errors.append(f"{package_manifest}: unexpected or ignored entry {relative}")
    for relative in sorted(set(expected_entries) - set(package_entries)):
        errors.append(f"{package_manifest}: unrecorded artifact {relative}")

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
