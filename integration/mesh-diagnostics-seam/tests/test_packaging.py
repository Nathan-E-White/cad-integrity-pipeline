"""Exercise the public build backend from a clean source tree."""
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.fixture
def clean_source(tmp_path):
    source = Path(__file__).parents[1]
    clean = tmp_path / "source"
    shutil.copytree(source, clean, ignore=shutil.ignore_patterns(
        "node_modules", "templates", "dist", "__pycache__", ".pytest_cache", ".core-build", "test-results"))
    return clean


def test_clean_wheel_build_refuses_missing_frontend(clean_source):
    clean = clean_source
    result = subprocess.run([sys.executable, "-m", "build", "--no-isolation", "--wheel", str(clean)],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode != 0
    assert "scripts/build_component.py" in result.stdout + result.stderr
    assert not list((clean / "dist").glob("*.whl"))


def test_editable_build_allows_frontend_bootstrap(clean_source):
    result = subprocess.run([sys.executable, "-c",
                             "from hatchling.build import build_editable; build_editable('dist')"],
                            cwd=clean_source, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert list((clean_source / "dist").glob("*.whl"))


def test_source_distribution_retains_build_guard(clean_source):
    import tarfile
    result = subprocess.run([sys.executable, "-m", "build", "--no-isolation", "--sdist", str(clean_source)],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    archive = next((clean_source / "dist").glob("*.tar.gz"))
    with tarfile.open(archive) as bundle:
        assert any(name.endswith("/hatch_build.py") for name in bundle.getnames())
