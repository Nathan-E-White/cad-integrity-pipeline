"""Internal checkout guardrails for the local inspection preview."""

from __future__ import annotations

import importlib
import os
import socket
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TextIO


class ModuleWithFile(Protocol):
    __file__: str | os.PathLike[str] | None


class PreviewError(RuntimeError):
    """A local preview preflight failure."""


@dataclass(frozen=True)
class CheckoutIdentity:
    root: Path
    branch: str
    commit: str
    dirty: bool
    port: int


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def inspect_checkout(root: Path, *, port: int) -> CheckoutIdentity:
    canonical_root = Path(_git(root, "rev-parse", "--show-toplevel")).resolve()
    branch = _git(canonical_root, "branch", "--show-current") or "(detached)"
    commit = _git(canonical_root, "rev-parse", "HEAD")
    dirty = bool(_git(canonical_root, "status", "--porcelain", "--untracked-files=no"))
    return CheckoutIdentity(canonical_root, branch, commit, dirty, port)


def _preview_port(environ: Mapping[str, str]) -> int:
    raw_port = environ.get("CAD_INTEGRITY_PREVIEW_PORT", "7863")
    try:
        port = int(raw_port)
    except ValueError as error:
        raise PreviewError(f"invalid CAD_INTEGRITY_PREVIEW_PORT: {raw_port!r}") from error
    if not 1 <= port <= 65535:
        raise PreviewError(f"CAD_INTEGRITY_PREVIEW_PORT must be between 1 and 65535: {port}")
    return port


def prepare_preview(
    root: Path,
    *,
    environ: Mapping[str, str],
    output: TextIO | None = None,
) -> CheckoutIdentity:
    identity = inspect_checkout(root, port=_preview_port(environ))
    stream = output if output is not None else sys.stdout
    print(f"repository: {identity.root}", file=stream)
    print(f"branch: {identity.branch}", file=stream)
    print(f"commit: {identity.commit}", file=stream)
    print(f"tracked state: {'dirty' if identity.dirty else 'clean'}", file=stream)
    print(f"port: {identity.port}", file=stream, flush=True)
    if environ.get("CAD_INTEGRITY_REQUIRE_CLEAN") == "1" and identity.dirty:
        raise PreviewError("clean checkout required, but tracked changes are present")
    return identity


def verify_canonical_checkout(identity: CheckoutIdentity) -> None:
    if identity.branch != "main":
        raise PreviewError(
            f"canonical main checkout required; active branch is {identity.branch}"
        )


def _expected_module_directories(root: Path) -> dict[str, Path]:
    return {
        "cad_integrity": root / "src/cad_integrity",
        "gradio_topologicaldeltaaudit": (
            root / "components/topological_delta_audit/backend/gradio_topologicaldeltaaudit"
        ),
        "gradio_verificationgrid": (
            root / "components/verification_grid/backend/gradio_verificationgrid"
        ),
        "gradio_inspectionworkspace": (
            root / "components/inspection_workspace/backend/gradio_inspectionworkspace"
        ),
    }


def verify_module_origins(
    root: Path,
    *,
    importer: Callable[[str], ModuleWithFile] = importlib.import_module,
    expected_directories: Mapping[str, Path] | None = None,
) -> None:
    expected = expected_directories or _expected_module_directories(root)
    for module_name, expected_directory in expected.items():
        module = importer(module_name)
        module_file = getattr(module, "__file__", None)
        if module_file is None:
            raise PreviewError(f"{module_name} has no filesystem origin")
        origin = Path(module_file).resolve()
        if not origin.is_relative_to(expected_directory.resolve()):
            raise PreviewError(
                f"{module_name} loaded outside canonical checkout: {origin}; "
                f"expected under {expected_directory.resolve()}"
            )


def ensure_port_available(host: str, port: int) -> None:
    with socket.socket() as candidate:
        try:
            candidate.bind((host, port))
        except OSError as error:
            raise PreviewError(f"port {port} is already occupied on {host}") from error


def launch_preview(root: Path, *, environ: Mapping[str, str]) -> None:
    identity = prepare_preview(root, environ=environ)
    verify_canonical_checkout(identity)
    verify_module_origins(identity.root)
    ensure_port_available("127.0.0.1", identity.port)

    from cad_integrity.gradio_app import build_app

    build_app().launch(
        server_name="127.0.0.1",
        server_port=identity.port,
        share=False,
    )


def main() -> int:
    try:
        launch_preview(Path(__file__).resolve().parents[1], environ=os.environ)
    except (PreviewError, subprocess.CalledProcessError) as error:
        print(f"inspection preview refused: {error}", file=sys.stderr)
        return 2
    return 0
