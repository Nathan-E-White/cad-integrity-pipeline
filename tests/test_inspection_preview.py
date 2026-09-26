from __future__ import annotations

import socket
import subprocess
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.inspection_preview import (
    PreviewError,
    ensure_port_available,
    inspect_checkout,
    prepare_preview,
    verify_canonical_checkout,
    verify_module_origins,
)


def _git(directory: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(directory), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _committed_checkout(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "checkout"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    tracked = repo / "tracked.txt"
    tracked.write_text("baseline\n")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", "baseline")
    return repo, tracked


def test_checkout_identity_reports_root_branch_commit_and_clean_state(tmp_path: Path) -> None:
    repo, _ = _committed_checkout(tmp_path)

    identity = inspect_checkout(repo, port=7863)

    assert identity.root == repo.resolve()
    assert identity.branch == "main"
    assert identity.commit == _git(repo, "rev-parse", "HEAD")
    assert identity.dirty is False
    assert identity.port == 7863


def test_preview_rejects_a_non_main_checkout(tmp_path: Path) -> None:
    repo, _ = _committed_checkout(tmp_path)
    _git(repo, "switch", "-c", "feature")

    with pytest.raises(PreviewError, match="canonical main checkout required"):
        verify_canonical_checkout(inspect_checkout(repo, port=7863))


@pytest.mark.parametrize(
    "module_name",
    [
        "cad_integrity",
        "gradio_topologicaldeltaaudit",
        "gradio_verificationgrid",
        "gradio_inspectionworkspace",
    ],
)
def test_preview_rejects_modules_loaded_outside_the_checkout(
    tmp_path: Path, module_name: str
) -> None:
    repo = tmp_path / "checkout"
    repo.mkdir()
    outside = tmp_path / "other-install" / module_name / "__init__.py"
    outside.parent.mkdir(parents=True)
    outside.touch()

    with pytest.raises(PreviewError, match=rf"{module_name}.*outside canonical checkout"):
        verify_module_origins(
            repo,
            importer=lambda requested: SimpleNamespace(
                __file__=(
                    outside
                    if requested == module_name
                    else repo / "expected" / requested / "__init__.py"
                )
            ),
            expected_directories={name: repo / "expected" / name for name in (
                "cad_integrity",
                "gradio_topologicaldeltaaudit",
                "gradio_verificationgrid",
                "gradio_inspectionworkspace",
            )},
        )


def test_preview_refuses_an_occupied_port() -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]

        with pytest.raises(PreviewError, match=rf"port {port} is already occupied"):
            ensure_port_available("127.0.0.1", port)


def test_clean_required_rejects_tracked_changes(tmp_path: Path) -> None:
    repo, tracked = _committed_checkout(tmp_path)
    tracked.write_text("changed\n")

    with pytest.raises(PreviewError, match="tracked changes"):
        prepare_preview(repo, environ={"CAD_INTEGRITY_REQUIRE_CLEAN": "1"})


def test_normal_development_reports_dirty_checkout(tmp_path: Path) -> None:
    repo, tracked = _committed_checkout(tmp_path)
    tracked.write_text("changed\n")
    output = StringIO()

    identity = prepare_preview(repo, environ={}, output=output)

    assert identity.dirty is True
    assert f"repository: {repo.resolve()}" in output.getvalue()
    assert "branch: main" in output.getvalue()
    assert f"commit: {_git(repo, 'rev-parse', 'HEAD')}" in output.getvalue()
    assert "tracked state: dirty" in output.getvalue()
    assert "port: 7863" in output.getvalue()


def test_preview_preserves_the_configured_port(tmp_path: Path) -> None:
    repo, _ = _committed_checkout(tmp_path)
    output = StringIO()

    identity = prepare_preview(
        repo,
        environ={"CAD_INTEGRITY_PREVIEW_PORT": "9123"},
        output=output,
    )

    assert identity.port == 9123
    assert "port: 9123" in output.getvalue()


def test_playwright_and_manual_tasks_use_the_same_launcher() -> None:
    root = Path(__file__).resolve().parents[1]
    project = (root / "pyproject.toml").read_text()
    playwright = (
        root / "components/inspection_workspace/frontend/playwright.config.ts"
    ).read_text()
    package = (
        root / "components/inspection_workspace/frontend/package.json"
    ).read_text()

    assert 'inspection-preview = "python scripts/run_inspection_preview.py"' in project
    assert 'gradio = { cmd = "python scripts/run_inspection_preview.py"' in project
    assert "pixi run inspection-preview" in playwright
    assert '"test:browser": "pixi run build-components && playwright test"' in package
