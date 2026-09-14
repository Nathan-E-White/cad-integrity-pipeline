#!/usr/bin/env python3
"""Fetch four GenCAD gallery pairs, not weights, into an independent asset directory.

Python 3.10+, standard library only. No inference, healing, or third-party code
execution. The two pathological cases remain explicit plans, not generated files.
Network transfer was not executable in the preparation environment; --list and
local content-validation logic were exercised. Upstream paths and blob IDs were
verified through GitHub. Preserve attribution and review asset reuse permissions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from urllib.request import Request, urlopen

COMMIT = "cc789e32e0831df4e15ff271fb0a0ffcfb54ef03"
BASE = f"https://raw.githubusercontent.com/gencad/gencad.github.io/{COMMIT}/"
MAX_BYTES = 5_000_000
# Each mesh record is: filename stem, upstream bytes, upstream Git blob SHA-1.
CASES = (
    ("V1-round-boss", "vanilla", "Round base with cylindrical boss", "sample_diversity_2", (
        ("sample_diversity_2_1", 12304, "c96c7d0d8a06d4def66a84d2ad31b0a2d63ddd8f"),
        ("sample_diversity_2_2", 12404, "2284acbe36a302c081fb31f8a846fc920be4a3f2"),
        ("sample_diversity_2_3", 5788, "e438e35c8eba0459800cf6163574b4e7b8ebc104"),
    )),
    ("V2-hex-spacer", "vanilla", "Hexagonal spacer with central bore", "sample_diversity_1", (
        ("sample_diversity_1_1", 4500, "b0ccefdc67096988b64a12a96b5aeaa181875382"),
        ("sample_diversity_1_2", 5172, "8f7359a1c9c55552bbf86fdb6305a307ae18bd31"),
        ("sample_diversity_1_3", 6340, "049d3a3e265f0cc6dc42b30fff58322b9a2a491f"),
    )),
    ("N1-slotted-flange", "neat", "Slotted annular part with thin flange", "386", (
        ("386", 18224, "c17b71c315ebb61feff3aa2f694d93d64931863f"),
    )),
    ("N2-two-hole-link", "neat", "Two-hole link with raised boss", "390", (
        ("390", 14384, "01958720ca3b027505977369edadeacb5ace449b"),
    )),
)

FIXTURE_PLANS = [
    {
        "id": "P1-detached-cap",
        "status": "planned_not_generated",
        "parent": "V1-round-boss",
        "origin": "deliberate fault injection, not an observed GenCAD defect",
        "precondition": "Audited, coherently oriented, closed manifold working mesh; recorded import policy.",
        "recipe": "Select a disk-like surface patch; duplicate its boundary vertex indices; translate the entire patch outward by delta; reverse all its triangles. Record patch IDs and transformations.",
        "suggested_delta": "1e-3 times the baseline bounding-box diagonal, provided this is small relative to local features",
        "expected_behavior": "Detect the disconnected/open patch. Test candidate stitching and orientation only under explicit correspondence and displacement budgets. Refuse if ambiguity or geometry checks fail.",
        "note": "The patch still exists: this is not missing-surface reconstruction. Success has not been measured.",
    },
    {
        "id": "P2-pinched-double-boss",
        "status": "planned_not_generated",
        "parent": "V1-round-boss",
        "origin": "deliberate fault injection, not an observed GenCAD defect",
        "precondition": "Audited closed manifold working mesh, plus a vertex p that uniquely maximizes n dot x for some direction n.",
        "recipe": "Duplicate the mesh using x'=2*p-x, reverse the copy's triangle winding, and identify only the two copies of p as one shared vertex. Unique support guarantees the copies meet only at p.",
        "expected_behavior": "Edge-incidence tests alone pass, but the link of the shared vertex has two components. Report nonmanifold; do not accept as one manifold boundary.",
        "note": "Separating topological vertex IDs does not remove geometric point contact. Choosing two solids versus a physical connection requires an explicit policy.",
    },
]


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def validate(data: bytes, source: str, size: int | None = None, oid: str | None = None) -> None:
    if not data or len(data) > MAX_BYTES:
        raise ValueError(f"Unexpected payload size for {source}: {len(data)}")
    if size is not None and len(data) != size:
        raise ValueError(f"Size mismatch for {source}: expected {size}, received {len(data)}")
    if oid is not None and git_blob_sha1(data) != oid:
        raise ValueError(f"Git blob hash mismatch for {source}")
    if source.endswith(".png") and not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"Not a PNG: {source}")
    if source.endswith(".glb"):
        if len(data) < 12 or data[:4] != b"glTF":
            raise ValueError(f"Not a GLB: {source}")
        _, version, length = struct.unpack("<4sII", data[:12])
        if version != 2 or length != len(data):
            raise ValueError(f"Invalid GLB header: {source}")


def write_new_or_identical(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise FileExistsError(f"Refusing symlink: {path}")
    if path.exists():
        if path.read_bytes() != data:
            raise FileExistsError(f"Refusing to replace different existing file: {path}")
        return
    try:
        with path.open("xb") as handle:
            handle.write(data)
    except FileExistsError:
        raise
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def download(out: Path, source: str, destination: str, timeout: float,
             size: int | None = None, oid: str | None = None) -> dict:
    url = BASE + source
    request = Request(url, headers={"User-Agent": "CAD-demo-case-fetcher/1.0"})
    with urlopen(request, timeout=timeout) as response:
        data = response.read(MAX_BYTES + 1)
    validate(data, source, size, oid)
    write_new_or_identical(out / destination, data)
    print(f"{len(data):>7} bytes  {destination}")
    return {"source_url": url, "source_path": source, "local_path": destination,
            "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "git_blob_sha1": git_blob_sha1(data), "modified": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("gencad-demo-cases"))
    parser.add_argument("--include-alternates", action="store_true",
                        help="Include all three published samples for each vanilla input.")
    parser.add_argument("--list", action="store_true", help="Show selections without downloading.")
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.list:
        for case_id, category, title, image_id, meshes in CASES:
            chosen = meshes if args.include_alternates else meshes[:1]
            print(f"{case_id}: {title}; {len(chosen)} mesh(es); {sum(m[1] for m in chosen)} mesh bytes")
        print("P1 and P2: fixture plans only; no pathological meshes are downloaded or generated.")
        return
    manifest = {"source_project": "GenCAD", "authors": ["Md Ferdous Alam", "Faez Ahmed"],
                "source_site": "https://gencad.github.io/", "source_commit": COMMIT,
                "representation": "author-published visualization meshes, not native STEP or raw inference tensors",
                "audit_status": "not_run", "units": "physical engineering dimensions not established",
                "license_note": "Upstream README declares website CC BY-SA 4.0. Retain attribution and confirm scope for mesh reuse before public hosting.",
                "cases": []}
    for case_id, category, title, image_id, meshes in CASES:
        assets = [download(args.out, f"static/images/{image_id}.png",
                           f"{case_id}/input.png", args.timeout)]
        for stem, size, oid in (meshes if args.include_alternates else meshes[:1]):
            assets.append(download(args.out, f"static/mesh/{stem}.glb",
                                   f"{case_id}/published/{stem}.glb", args.timeout, size, oid))
        manifest["cases"].append({"id": case_id, "category": category, "title": title, "assets": assets})
    manifest["source_notice"] = download(args.out, "README.md", "UPSTREAM_README.md", args.timeout,
                                         829, "3e4fe474dafe184ddd54f659304d089b7b04a7d5")
    for filename, obj in (("manifest.json", manifest), ("fixture-plans.json", FIXTURE_PLANS)):
        write_new_or_identical(args.out / filename, (json.dumps(obj, indent=2) + "\n").encode())
    print("Done. Assets are unchanged; no inference, geometry audit, or repair was executed.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Download stopped: {exc}") from exc
