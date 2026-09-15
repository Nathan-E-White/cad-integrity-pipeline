import tomllib
from pathlib import Path


def test_pythonocc_core_is_declared_only_for_conda_resolution() -> None:
    project = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8"))

    assert "pythonocc-core" not in project["project"]["dependencies"]
    assert "pythonocc-core" in project["tool"]["pixi"]["dependencies"]
