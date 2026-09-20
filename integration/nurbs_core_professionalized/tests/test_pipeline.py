import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from main import PipelineConfig, main, run_pipeline
from NURBSCoreEngine import GeometryValidationError


def test_json_pipeline_and_output_safety(plane_stl, tmp_path):
    path = tmp_path / "cards.json"
    config = PipelineConfig(plane_stl, path, units="mm")
    result = run_pipeline(config)
    assert result.complete
    assert result.published_paths == (path,)
    assert result.publication_error is None
    assert result.step_path is None
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
    assert result.complete
    assert result.published_paths == (result.cards_path, result.step_path)
    assert result.publication_error is None


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


@pytest.mark.step
def test_step_publication_failure_returns_partial_result(plane_stl, tmp_path, monkeypatch):
    pytest.importorskip("OCP")
    cards_path, step_path = tmp_path / "cards.json", tmp_path / "model.step"
    original_link = os.link

    def fail_step(source, destination, *args, **kwargs):
        if Path(destination) == step_path:
            raise PermissionError(13, "STEP publication denied", str(destination))
        return original_link(source, destination, *args, **kwargs)

    monkeypatch.setattr(os, "link", fail_step)
    result = run_pipeline(PipelineConfig(plane_stl, cards_path, step_path, units="mm"))
    assert not result.complete
    assert result.published_paths == (cards_path,)
    assert result.publication_error.path == step_path
    assert result.publication_error.error_type == "PermissionError"
    assert result.publication_error.errno == 13
    assert "STEP publication denied" in result.publication_error.message
    assert result.cards == json.loads(cards_path.read_text())
    assert result.primitive_count == 1
    assert result.valid_feature_count == result.input_vertices
    assert result.elapsed_seconds >= 0
    assert not step_path.exists()
    assert not list(tmp_path.glob(".*.tmp"))


def test_json_write_failure_returns_computed_result(plane_stl, tmp_path, monkeypatch):
    path = tmp_path / "cards.json"

    def fail_link(*args, **kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "link", fail_link)
    result = run_pipeline(PipelineConfig(plane_stl, path))
    assert not result.complete
    assert result.published_paths == ()
    assert result.publication_error.path == path
    assert result.publication_error.errno == 28
    assert result.cards["operations"][0]["primitive"] == "PLANE"
    assert result.primitive_count == 1
    assert not path.exists()


@pytest.mark.step
@pytest.mark.parametrize("overwrite", [False, True])
@pytest.mark.parametrize("failed_output", ["cards.json", "model.step"])
def test_cli_reports_only_confirmed_outputs_on_write_failure(
    plane_stl, tmp_path, monkeypatch, caplog, overwrite, failed_output,
):
    pytest.importorskip("OCP")
    cards_path, step_path = tmp_path / "cards.json", tmp_path / "model.step"
    if overwrite:
        cards_path.write_text("old JSON")
        step_path.write_text("old STEP")
    operation = "replace" if overwrite else "link"
    original = getattr(os, operation)

    def fail_publication(source, destination, *args, **kwargs):
        if Path(destination).name == failed_output:
            raise OSError(28, "No space left on device", str(destination))
        return original(source, destination, *args, **kwargs)

    monkeypatch.setattr(os, operation, fail_publication)
    caplog.set_level("INFO", logger="main")
    args = [str(plane_stl), "--cards", str(cards_path), "--step", str(step_path), "--units", "mm"]
    assert main(args + (["--overwrite"] if overwrite else [])) == 2
    assert f"Publication failed: {tmp_path / failed_output}" in caplog.text
    assert "No space left on device" in caplog.text
    assert f"STEP: {step_path}" not in caplog.text
    assert (f"JSON: {cards_path}" in caplog.text) == (failed_output == "model.step")
    if failed_output == "cards.json":
        assert cards_path.read_text() == "old JSON" if overwrite else not cards_path.exists()
    else:
        assert json.loads(cards_path.read_text())["operations"][0]["primitive"] == "PLANE"
    assert step_path.read_text() == "old STEP" if overwrite else not step_path.exists()
    assert not list(tmp_path.glob(".*.tmp"))
