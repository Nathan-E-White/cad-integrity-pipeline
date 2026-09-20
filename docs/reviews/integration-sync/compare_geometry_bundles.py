"""Inventory archive/live paths and Python interfaces without executing deliveries."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[3]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def symbols(data):
    result = []

    def visit(node, prefix=""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + child.name
                result.append({"name": name, "line": child.lineno, "end_line": child.end_lineno})
                visit(child, name + ".")
            else:
                visit(child, prefix)

    visit(ast.parse(data.decode()))
    return result


def compare(name, filename):
    base = ROOT / "integration" / name
    archive = base / filename
    if filename.endswith(".zip"):
        with zipfile.ZipFile(archive) as source:
            entries = [(n, source.read(n)) for n in source.namelist() if not n.endswith("/")]
    else:
        with tarfile.open(archive) as source:
            entries = [(m.name, source.extractfile(m).read()) for m in source.getmembers() if m.isfile()]
    files = {}
    for path, data in entries:
        parts = PurePosixPath(path).parts
        if parts[0] != name or ".." in parts:
            raise ValueError(path)
        relative = str(PurePosixPath(*parts[1:]))
        if relative in files:
            raise ValueError(f"Duplicate member: {relative}")
        live = base / relative
        current = live.read_bytes() if live.is_file() else None
        record = {"archive_sha256": sha(data),
                  "live_sha256": sha(current) if current is not None else None,
                  "state": "missing" if current is None else "equal" if current == data else "changed"}
        if relative.endswith(".py"):
            record["archive_symbols"] = symbols(data)
            record["live_symbols"] = symbols(current) if current is not None else []
        files[relative] = record
    return {"archive_sha256": sha(archive.read_bytes()), "archive_file_count": len(files),
            "counts": {s: sum(r["state"] == s for r in files.values()) for s in ("equal", "changed", "missing")},
            "files": dict(sorted(files.items()))}


if __name__ == "__main__":
    print(json.dumps({name: compare(name, filename) for name, filename in (
        ("mesh_healing_extension", "mesh_healing_extension.tar.gz"),
        ("nurbs_core_professionalized", "nurbs_core_professionalized.zip"),
    )}, indent=2, sort_keys=True))
