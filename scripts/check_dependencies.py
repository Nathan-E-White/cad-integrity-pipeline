"""Check shared declarations and local package relationships without installing."""
from __future__ import annotations

import argparse
import json
import sys
import tomllib
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as installed_version
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]


def resolved_vtk_errors(root: Path, pixi_environment: str) -> list[str]:
    """Inspect the selected environment, not the lock's shared package inventory."""
    try:
        lock = yaml.safe_load((root / "pixi.lock").read_text())
        if lock["version"] != 7:
            return ["pixi.lock: expected supported lock version 7"]
        platforms = lock["environments"][pixi_environment]["packages"]
        if not isinstance(platforms, dict) or not platforms:
            raise ValueError("selected environment has no platform resolutions")
        errors = []
        for platform, packages in platforms.items():
            if not isinstance(packages, list) or not packages:
                raise ValueError(f"{platform}: missing package resolution")
            for package in packages:
                if "conda" not in package:
                    continue
                filename = unquote(urlsplit(package["conda"]).path.rsplit("/", 1)[-1])
                if filename.endswith(".conda"):
                    stem = filename.removesuffix(".conda")
                elif filename.endswith(".tar.bz2"):
                    stem = filename.removesuffix(".tar.bz2")
                else:
                    raise ValueError(f"unsupported conda artifact: {filename}")
                name, _, _ = stem.rsplit("-", 2)
                if name == "vtk" or name.startswith("vtk-"):
                    errors.append(
                        f"pixi.lock {pixi_environment}/{platform}: resolved conda VTK provider "
                        f"{name}; CAD environment requires PyPI-owned VTK"
                    )
        return errors
    except (OSError, yaml.YAMLError, KeyError, TypeError, ValueError) as exc:
        return [f"pixi.lock: cannot inspect environment {pixi_environment!r}: {exc}"]


def check(root: Path, *, environment: bool = False, pixi_environment: str = "default") -> list[str]:
    errors: list[str] = resolved_vtk_errors(root, pixi_environment)
    policy = tomllib.loads((root / "dependency-policy.toml").read_text())["python"]
    constraints = [Requirement(line) for line in (root / "requirements/constraints.txt").read_text().splitlines()
                   if line.strip() and not line.startswith("#")]
    if {canonicalize_name(r.name) for r in constraints} != set(policy) - {"setuptools"}:
        errors.append("portable constraints must cover the shared runtime/test dependencies")
    for requirement in constraints:
        name = canonicalize_name(requirement.name)
        pins = list(requirement.specifier)
        if len(pins) != 1 or pins[0].operator != "==" or "*" in pins[0].version:
            errors.append(f"portable constraint for {name} must be exact")
            continue
        if name not in policy or pins[0].version not in Requirement(name + policy[name]).specifier:
            errors.append(f"portable constraint for {name} violates the shared policy")
        if environment:
            try:
                installed = installed_version(name)
            except PackageNotFoundError:
                errors.append(f"shared environment dependency {name} is not installed")
            else:
                if installed not in requirement.specifier:
                    errors.append(f"installed {name}=={installed} differs from {requirement}")
    parent = tomllib.loads((root / "pyproject.toml").read_text())
    conda = parent["tool"]["pixi"]["dependencies"]
    pythonocc = conda.get("pythonocc-core", {})
    if (not isinstance(pythonocc, dict) or pythonocc.get("build") != "novtk*"
            or {"vtk", "vtk-base", "vtk-io-ffmpeg"} & conda.keys()):
        errors.append("CAD environment must use PythonOCC novtk and PyPI-owned VTK")
    python_specs: dict[str, set[str]] = {}
    projects = [root / "pyproject.toml", *sorted((root / "components").glob("*/pyproject.toml")),
                *sorted((root / "integration").glob("*/pyproject.toml"))]
    for path in projects:
        data = tomllib.loads(path.read_text())
        declarations = [*data["project"].get("dependencies", []),
                        *data.get("build-system", {}).get("requires", [])]
        for group in data["project"].get("optional-dependencies", {}).values():
            declarations.extend(group)
        for value in declarations:
            requirement = Requirement(value)
            name = canonicalize_name(requirement.name)
            python_specs.setdefault(name, set()).add(str(requirement.specifier))
            if name in policy and str(requirement.specifier) != str(Requirement(name + policy[name]).specifier):
                errors.append(f"{path.relative_to(root)}: {value} differs from shared {name}{policy[name]}")
    for name, specs in python_specs.items():
        if len(specs) > 1:
            errors.append(f"Python children declare conflicting ranges for {name}: {sorted(specs)}")

    # These files mirror the mesh-healing optional dependency groups.
    healing = root / "integration/mesh_healing_extension"
    data = tomllib.loads((healing / "pyproject.toml").read_text())["project"]
    for file, expected in (
        ("requirements.txt", data["dependencies"]),
        ("requirements-step.txt", ["-r requirements.txt", *data["optional-dependencies"]["step"]]),
        ("requirements-dev.txt", ["-r requirements-step.txt", *data["optional-dependencies"]["test"]]),
    ):
        actual = [line.strip() for line in (healing / file).read_text().splitlines()
                  if line.strip() and not line.startswith("#")]
        if actual != expected:
            errors.append(f"{healing.relative_to(root) / file}: differs from pyproject dependencies")

    package = json.loads((root / "package.json").read_text())
    workspaces = package["workspaces"]["packages"]
    catalog = package["workspaces"]["catalog"]
    ui = {canonicalize_name(r.name): r for r in map(Requirement, parent["project"]["optional-dependencies"]["ui"])}
    for component in sorted((root / "components").glob("*/pyproject.toml")):
        project = tomllib.loads(component.read_text())["project"]
        name, version = canonicalize_name(project["name"]), project["version"]
        if name not in ui or str(ui[name].specifier) != f"=={version}":
            errors.append(f"root ui extra must require {name}=={version}")
        local = parent["tool"]["pixi"]["pypi-dependencies"].get(name, {})
        if local.get("path") != component.parent.relative_to(root).as_posix():
            errors.append(f"Pixi must resolve {name} from its local component directory")
        frontend = json.loads((component.parent / "frontend/package.json").read_text())
        if frontend["version"] != version:
            errors.append(f"{component.parent.relative_to(root)}: Python/frontend package versions differ")
        requirement = Requirement((component.parent / "demo/requirements.txt").read_text().strip())
        if canonicalize_name(requirement.name) != name or str(requirement.specifier) != f"=={version}":
            errors.append(f"{component.parent.relative_to(root)}: demo dependency differs")

    actual_workspaces = {p.parent.relative_to(root).as_posix()
                         for pattern in ("components/*/frontend/package.json", "integration/*/package.json")
                         for p in root.glob(pattern)}
    if set(workspaces) != actual_workspaces:
        errors.append("root JavaScript workspace list differs from child package inventory")
    javascript_specs: dict[str, set[str]] = {}
    for workspace in workspaces:
        child = json.loads((root / workspace / "package.json").read_text())
        for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            for name, version in child.get(section, {}).items():
                javascript_specs.setdefault(name, set()).add(version)
                if name in catalog and version != "catalog:":
                    errors.append(f"{workspace}: {name} must use the root catalog")
                if version == "catalog:" and name not in catalog:
                    errors.append(f"{workspace}: unresolved catalog entry {name}")
        for filename in ("bun.lock", "bun.lockb", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"):
            if (root / workspace / filename).exists():
                errors.append(f"{workspace}/{filename}: child lockfile competes with root bun.lock")
    for name, specs in javascript_specs.items():
        if len(specs) > 1:
            errors.append(f"JavaScript children declare conflicting ranges for {name}: {sorted(specs)}")
    if not (root / "bun.lock").is_file():
        errors.append("root bun.lock is missing")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", action="store_true", help="check installed shared versions")
    parser.add_argument("--pixi-environment", default="default", help="resolved lock environment (default: default)")
    args = parser.parse_args()
    errors = check(ROOT, environment=args.environment, pixi_environment=args.pixi_environment)
    if errors:
        print("\n".join(errors))
        return 1
    print("Dependency declarations, resolved VTK ownership and parent/child relationships verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
