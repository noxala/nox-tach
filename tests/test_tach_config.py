# tests/test_tach_config.py
from __future__ import annotations

from pathlib import Path

import pytest

from nox_tach.tach_config import (
    parse_tach_config,
    source_path_for_module,
    top_level_python_packages,
)


def _tach_text(*, source_roots: str = '["."]') -> str:
    return f"""\
source_roots = {source_roots}
exact = true
root_module = "forbid"

[[modules]]
path = "pkg"
depends_on = []
"""


def test_parse_tach_config_reads_multiple_source_roots() -> None:
    config = parse_tach_config(_tach_text(source_roots='["src", "generated"]'))

    assert config.source_roots == (Path("src"), Path("generated"))
    assert config.module_paths == frozenset({"pkg"})


def test_parse_tach_config_defaults_source_root_to_repository_root() -> None:
    config = parse_tach_config(
        """\
exact = true
root_module = "forbid"

[[modules]]
path = "pkg"
depends_on = []
"""
    )

    assert config.source_roots == (Path("."),)


def test_source_path_for_module_resolves_directory_under_source_root(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "src" / "pkg" / "feature"
    directory.mkdir(parents=True)

    resolved = source_path_for_module(
        repo_root=tmp_path,
        source_roots=(Path("src"),),
        module_path="pkg.feature",
    )

    assert resolved.path == directory
    assert resolved.source_root == Path("src")
    assert resolved.is_directory is True


def test_source_path_for_module_resolves_single_file_module(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "src"
    source_root.mkdir()
    module = source_root / "standalone.py"
    module.write_text("value = 1\n", encoding="utf-8")

    resolved = source_path_for_module(
        repo_root=tmp_path,
        source_roots=(Path("src"),),
        module_path="standalone",
    )

    assert resolved.path == module
    assert resolved.is_directory is False


def test_top_level_python_packages_scans_all_source_roots(tmp_path: Path) -> None:
    for source_root, package_name in (("src", "alpha"), ("generated", "beta")):
        package = tmp_path / source_root / package_name
        package.mkdir(parents=True)
        package.joinpath("__init__.py").write_text("", encoding="utf-8")

    assert top_level_python_packages(
        repo_root=tmp_path,
        source_roots=(Path("src"), Path("generated")),
    ) == frozenset({"alpha", "beta"})


def test_top_level_python_packages_rejects_ambiguous_package_roots(
    tmp_path: Path,
) -> None:
    for source_root in ("src", "generated"):
        package = tmp_path / source_root / "shared"
        package.mkdir(parents=True)
        package.joinpath("__init__.py").write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="exists in multiple Tach source roots"):
        top_level_python_packages(
            repo_root=tmp_path,
            source_roots=(Path("src"), Path("generated")),
        )
