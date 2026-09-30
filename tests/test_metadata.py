"""Keep Cargo's required package metadata aligned with Python's canonical metadata."""

from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_cargo_name_and_version_mirror_pyproject() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    cargo = tomllib.loads((ROOT / "Cargo.toml").read_text(encoding="utf-8"))

    project = pyproject["project"]
    package = cargo["package"]
    assert package["name"] == project["name"], "Cargo package name must mirror pyproject [project].name"
    assert package["version"] == project["version"], "Cargo package version must mirror pyproject [project].version"
