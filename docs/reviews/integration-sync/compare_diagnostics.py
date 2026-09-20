"""Read delivery bytes and ASTs; never extract or execute supplied modules.

Run from any directory with Python 3.11+. Output is deterministic JSON on stdout.
Python symbols include nested functions/methods; TS symbols are a lexical aid only.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

ROOT = Path(__file__).resolve().parents[3]
LOOSE = ROOT / "integration/mesh-diagnostics-seam"
ARCHIVE = LOOSE / "mesh-diagnostics-seams.tar.gz"


def describe(data: bytes, path: str) -> dict:
    result = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    if path.endswith(".py"):
        tree = ast.parse(data.decode("utf-8"))
        symbols = []

        def walk(node, prefix=""):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = prefix + child.name
                    symbols.append({"name": name, "line": child.lineno,
                                    "kind": type(child).__name__})
                    walk(child, name + ".")
                else:
                    walk(child, prefix)

        walk(tree)
        result["symbols"] = symbols
        result["imports"] = [
            {"line": n.lineno, "source": ast.get_source_segment(data.decode(), n)}
            for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
        ]
    elif path.endswith((".ts", ".svelte")):
        result["lexical_declarations_and_tests"] = [
            {"line": i, "source": line.strip()}
            for i, line in enumerate(data.decode().splitlines(), 1)
            if re.search(r"\b(export (?:function|class|interface|type|const)|test\(|import )", line)
        ]
    return result


def main():
    archive = {}
    with tarfile.open(ARCHIVE) as source:
        for member in source.getmembers():
            if not member.isfile():
                continue
            path = PurePosixPath(member.name)
            if path.parts[0] != "mesh-diagnostics-seams" or ".." in path.parts:
                raise ValueError(f"Unexpected archive path: {member.name}")
            relative = str(PurePosixPath(*path.parts[1:]))
            if relative in archive:
                raise ValueError(f"Duplicate member: {relative}")
            archive[relative] = describe(source.extractfile(member).read(), relative)
        checksums = source.extractfile("mesh-diagnostics-seams/CHECKSUMS.sha256").read().decode()
    checksum_errors = []
    checksum_count = 0
    for line in checksums.splitlines():
        expected, path = line.split(maxsplit=1)
        checksum_count += 1
        if path not in archive or archive[path]["sha256"] != expected:
            checksum_errors.append(path)
    # The delivered loose source is flat. Do not inventory installed node_modules.
    loose = {p.name: describe(p.read_bytes(), p.name) for p in sorted(LOOSE.iterdir())
             if p.is_file() and p != ARCHIVE}
    same_path = []
    basename_candidates = []
    for path, info in sorted(archive.items()):
        if path in loose:
            same_path.append({"archive": path, "loose": path,
                              "equal": info["sha256"] == loose[path]["sha256"]})
        basename = PurePosixPath(path).name
        if basename in loose:
            basename_candidates.append({"archive": path, "loose": basename,
                                        "equal": info["sha256"] == loose[basename]["sha256"]})
    report = {
        "archive_path": str(ARCHIVE.relative_to(ROOT)),
        "archive_sha256": hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
        "method": "Archive root stripped; exact relative paths first. Basenames are candidates, not equivalence.",
        "archive_file_count": len(archive), "loose_file_count_excluding_archive": len(loose),
        "archive_manifest_entries": checksum_count,
        "archive_manifest_errors": checksum_errors,
        "same_relative_path": same_path, "basename_candidates": basename_candidates,
        "archive": dict(sorted(archive.items())), "loose": loose,
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
