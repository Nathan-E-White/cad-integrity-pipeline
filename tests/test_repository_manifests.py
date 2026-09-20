"""Regression checks for source inventory and dependency drift."""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_artifact_inventory_respects_ignore_rules_without_hiding_tracked_files(tmp_path, monkeypatch):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    (tmp_path / '.gitignore').write_text('.DS_Store\nnode_modules/\n*.generated\n')
    tracked = tmp_path / 'important.generated'
    tracked.write_text('tracked evidence')
    subprocess.run(['git', '-C', str(tmp_path), 'add', '-f', 'important.generated'], check=True)
    (tmp_path / '.DS_Store').write_bytes(b'finder')
    (tmp_path / 'node_modules').mkdir()
    (tmp_path / 'node_modules' / 'dependency.js').write_text('irrelevant')
    (tmp_path / 'new source.py').write_text('new untracked source')
    (tmp_path / 'SHA256SUMS.json').write_text('{}')
    script = load_script('verify_artifacts')
    monkeypatch.setattr(script, 'ROOT', tmp_path)
    entries = script.project_entries()
    assert set(entries) == {'.gitignore', 'important.generated', 'new source.py'}
    tracked.write_text('changed evidence')
    errors = script.verify_mapping(tmp_path, tmp_path / 'SHA256SUMS.json', entries)
    assert any('digest mismatch for important.generated' in error for error in errors)
    tracked.unlink()
    assert any('missing important.generated' in error for error in script.verify_mapping(
        tmp_path, tmp_path / 'SHA256SUMS.json', entries))


def manifest_copy(tmp_path):
    paths = ['pyproject.toml', 'dependency-policy.toml', 'package.json', 'bun.lock',
             'requirements/constraints.txt']
    for pattern in ['components/*/pyproject.toml', 'components/*/frontend/package.json',
                    'components/*/demo/requirements.txt', 'integration/*/pyproject.toml',
                    'integration/*/package.json', 'integration/mesh_healing_extension/requirements*.txt']:
        paths.extend(str(p.relative_to(ROOT)) for p in ROOT.glob(pattern))
    for path in paths:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / path, target)


@pytest.mark.parametrize('mutation,expected', [
    ('python', 'differs from shared numpy'),
    ('javascript', 'svelte must use the root catalog'),
    ('component', 'root ui extra must require'),
    ('lockfile', 'child lockfile competes'),
    ('cad-provider', 'PyPI-owned VTK'),
])
def test_dependency_check_rejects_independent_child_drift(tmp_path, mutation, expected):
    manifest_copy(tmp_path)
    script = load_script('check_dependencies')
    assert script.check(tmp_path) == []
    if mutation == 'python':
        path = tmp_path / 'integration/mesh_healing_extension/pyproject.toml'
        path.write_text(path.read_text().replace('numpy>=1.26,<3', 'numpy>=1.24,<3'))
    elif mutation == 'javascript':
        path = tmp_path / 'components/verification_grid/frontend/package.json'
        data = json.loads(path.read_text())
        data['dependencies']['svelte'] = '5.48.0'
        path.write_text(json.dumps(data))
    elif mutation == 'component':
        path = tmp_path / 'components/verification_grid/pyproject.toml'
        path.write_text(path.read_text().replace('version = "0.0.1"', 'version = "0.0.2"'))
    elif mutation == 'cad-provider':
        path = tmp_path / 'pyproject.toml'
        path.write_text(path.read_text().replace(
            '[tool.pixi.dependencies]', '[tool.pixi.dependencies]\nvtk = ">=9"'))
    else:
        (tmp_path / 'integration/mesh-diagnostics-seam/bun.lock').write_text('{}')
    assert any(expected in error for error in script.check(tmp_path))


def test_environment_check_reports_installed_version_drift(tmp_path, monkeypatch):
    manifest_copy(tmp_path)
    script = load_script('check_dependencies')
    from packaging.requirements import Requirement
    pins = {r.name: next(iter(r.specifier)).version for r in (
        Requirement(line) for line in (tmp_path / 'requirements/constraints.txt').read_text().splitlines()
        if line and not line.startswith('#'))}
    monkeypatch.setattr(script, 'installed_version', lambda name: pins[name])
    assert script.check(tmp_path, environment=True) == []
    pins['cadquery'] = '0.0.0'
    assert any('installed cadquery==0.0.0' in error
               for error in script.check(tmp_path, environment=True))

