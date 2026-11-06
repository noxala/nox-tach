# dev/tests/nox_tach_test/imports_test.py
from __future__ import annotations

from pathlib import Path

from nox_tach.imports import find_blacklisted_imports


def test_find_blacklisted_imports_honors_external_whitelist(tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    package.mkdir()
    package.joinpath("__init__.py").write_text("import pytest\n", encoding="utf-8")

    violations = find_blacklisted_imports(package, package="pkg")
    assert len(violations) == 1
    assert violations[0].imported_module == "pytest"

    assert (
        find_blacklisted_imports(
            package,
            package="pkg",
            whitelist=frozenset({"pytest"}),
        )
        == ()
    )
