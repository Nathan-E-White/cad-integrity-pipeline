"""Repository policy checks for visual prototypes and production build inputs."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_guard():
    path = ROOT / "scripts/check_prototype_status.py"
    spec = importlib.util.spec_from_file_location("check_prototype_status", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repository: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _prototype_repository(tmp_path: Path) -> tuple[Path, str]:
    repository = tmp_path / "repository"
    prototype = repository / "components/widget/frontend/prototypes/reference"
    prototype.mkdir(parents=True)
    (prototype / "index.html").write_text("baseline\n")
    (repository / "prototype-status.toml").write_text(
        "version = 1\n\n"
        "[[prototype]]\n"
        'path = "components/widget/frontend/prototypes/reference"\n'
        'status = "read_only"\n'
    )
    _git(repository, "init", "-q", "-b", "main")
    _git(repository, "config", "user.name", "Test User")
    _git(repository, "config", "user.email", "test@example.invalid")
    _git(repository, "config", "commit.gpgsign", "false")
    _git(repository, "add", ".")
    _git(repository, "commit", "-q", "-m", "baseline")
    return repository, _git(repository, "rev-parse", "HEAD")


def test_read_only_prototype_change_is_rejected(tmp_path: Path) -> None:
    repository, base = _prototype_repository(tmp_path)
    (repository / "components/widget/frontend/prototypes/reference/index.html").write_text(
        "changed\n"
    )

    errors = _load_guard().check_repository(
        repository,
        manifest_path=Path("prototype-status.toml"),
        base=base,
        head=None,
    )

    assert errors == [
        "read_only prototype changed: "
        "components/widget/frontend/prototypes/reference/index.html; "
        "promote components/widget/frontend/prototypes/reference to active in "
        "prototype-status.toml in the same change"
    ]


def test_same_change_can_explicitly_promote_prototype_to_active(tmp_path: Path) -> None:
    repository, base = _prototype_repository(tmp_path)
    (repository / "components/widget/frontend/prototypes/reference/index.html").write_text(
        "changed\n"
    )
    manifest = repository / "prototype-status.toml"
    manifest.write_text(manifest.read_text().replace('status = "read_only"', 'status = "active"'))

    assert (
        _load_guard().check_repository(
            repository,
            manifest_path=Path("prototype-status.toml"),
            base=base,
            head=None,
        )
        == []
    )


def test_repository_manifest_covers_each_prototype_directory() -> None:
    guard = _load_guard()
    manifest = Path("components/inspection_workspace/frontend/prototype-status.toml")
    entries = guard.load_manifest(ROOT / manifest)
    prototype_root = ROOT / "components/inspection_workspace/frontend/prototypes"
    directories = {
        path.relative_to(ROOT).as_posix() for path in prototype_root.iterdir() if path.is_dir()
    }

    assert set(entries) == directories
    assert {entry.status for entry in entries.values()} == {"read_only"}


def test_production_svelte_import_graph_excludes_prototypes() -> None:
    guard = _load_guard()
    frontend = ROOT / "components/inspection_workspace/frontend"

    imports = guard.production_import_graph(
        frontend,
        entrypoints=(Path("Index.svelte"), Path("Example.svelte")),
    )

    assert imports
    assert all("prototypes" not in path.parts for path in imports)
