import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from NURBSCoreEngine import GeometryValidationError
from main import PipelineConfig, main, run_pipeline


def test_json_pipeline_and_output_safety(plane_stl, tmp_path):
    path = tmp_path / "cards.json"
    config = PipelineConfig(plane_stl, path, units="mm")
    result = run_pipeline(config)
    assert result.primitive_count == 1
    assert result.valid_feature_count == result.input_vertices
    assert result.unassigned_count == 0
    cards = json.loads(path.read_text())
    assert cards["operations"][0]["primitive"] == "PLANE"
    assert cards["provenance"]["pipeline_settings"]["seed"] == 42
    with pytest.raises(FileExistsError):
        run_pipeline(config)
    original = plane_stl.read_bytes()
    with pytest.raises(GeometryValidationError, match="distinct"):
        run_pipeline(PipelineConfig(plane_stl, plane_stl, overwrite=True))
    assert original == plane_stl.read_bytes()


def test_cli_exit_codes_and_missing_units(plane_stl, tmp_path):
    assert main([str(plane_stl), "--cards", str(tmp_path / "a.json")]) == 0
    assert main([str(plane_stl), "--cards", str(tmp_path / "a.json")]) == 2
    assert main([str(tmp_path / "missing.stl")]) == 2
    assert main([str(plane_stl), "--step", str(tmp_path / "a.step")]) == 2


@pytest.mark.step
def test_full_pipeline_step(plane_stl, tmp_path):
    pytest.importorskip("OCP")
    result = run_pipeline(PipelineConfig(plane_stl, tmp_path / "cards.json", tmp_path / "model.step", units="mm"))
    assert result.primitive_count == 1
    assert result.step_path.read_text().startswith("ISO-10303-21;")


def test_imports_have_no_file_side_effects_and_do_not_need_ocp(tmp_path):
    root = Path(__file__).resolve().parents[1]
    code = '''
import builtins
original = builtins.__import__
def blocked(name, *args, **kwargs):
    if name == 'OCP' or name.startswith('OCP.'):
        raise ImportError('OCP deliberately blocked')
    return original(name, *args, **kwargs)
builtins.__import__ = blocked
import STLReader
import NURBSCoreEngine
import main
'''
    environment = dict(os.environ, PYTHONPATH=str(root), PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert result.stdout == result.stderr == ""
    assert list(tmp_path.iterdir()) == []
