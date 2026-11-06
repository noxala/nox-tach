# dev/tests/nox_tach_test/runner_test.py
from __future__ import annotations

from pathlib import Path

import pytest

from nox_tach import runner
from nox_tach.config import ModulePolicy
from nox_tach.imports import validate_external_lib_whitelists
from nox_tach.runner import validate_top_level_packages
from nox_tach.tach_config import parse_tach_config
from tests._helpers import assert_raises_msg


def _tach(*, module_path: str) -> str:
    return f"""\
source_roots = ["src"]
exact = true
root_module = "forbid"

[[modules]]
path = "{module_path}"
depends_on = []
"""


def _write_pyproject(tmp_path: Path) -> Path:
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        """\
[tool.ruff.lint.isort]
known-first-party = ["stale"]
known-third-party = ["alembic"]
""",
        encoding="utf-8",
    )
    return pyproject_path


def _write_runner_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    source_root = tmp_path / "src"
    for package_name in ("apkg", "zpkg"):
        package = source_root / package_name
        package.mkdir(parents=True)
        package.joinpath("__init__.py").write_text("", encoding="utf-8")

    tach_path = tmp_path / "tach.toml"
    tach_path.write_text(
        """\
source_roots = ["src"]
exact = true
root_module = "forbid"

[[modules]]
path = "zpkg"
depends_on = []

[[modules]]
path = "apkg"
depends_on = []
""",
        encoding="utf-8",
    )
    policy_path = tmp_path / "nox_tach.toml"
    policy_path.write_text("", encoding="utf-8")
    return tach_path, policy_path, _write_pyproject(tmp_path)


@pytest.mark.parametrize("fix", [False, True], ids=["check", "fix"])
def test_missing_source_roots_rejects_before_writing(tmp_path: Path, fix: bool) -> None:
    paths = _write_runner_fixture(tmp_path)
    tach_path, policy_path, pyproject_path = paths
    tach_path.write_text(
        tach_path.read_text().replace('source_roots = ["src"]\n', ""),
        encoding="utf-8",
    )
    before = tuple(path.read_bytes() for path in paths)

    with pytest.raises(ValueError, match="must explicitly declare source_roots"):
        runner.run(
            fix=fix,
            tach_path=tach_path,
            policy_path=policy_path,
            pyproject_path=pyproject_path,
        )

    assert tuple(path.read_bytes() for path in paths) == before


def test_top_level_package_validation_uses_configured_source_root(
    tmp_path: Path,
) -> None:
    package = tmp_path / "src" / "pkg"
    package.mkdir(parents=True)
    package.joinpath("__init__.py").write_text("", encoding="utf-8")
    tach = parse_tach_config(_tach(module_path="pkg"))

    validate_top_level_packages(repo_root=tmp_path, tach=tach)


def test_fix_rejects_missing_top_level_package(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    for package_name in ("declared", "missing"):
        package = source_root / package_name
        package.mkdir(parents=True)
        package.joinpath("__init__.py").write_text("", encoding="utf-8")

    tach_path = tmp_path / "tach.toml"
    tach_path.write_text(_tach(module_path="declared"), encoding="utf-8")
    policy_path = tmp_path / "nox_tach.toml"
    policy_path.write_text("", encoding="utf-8")
    pyproject_path = _write_pyproject(tmp_path)

    with pytest.raises(RuntimeError, match="Missing top-level packages: 'missing'"):
        runner.run(
            fix=True,
            tach_path=tach_path,
            policy_path=policy_path,
            pyproject_path=pyproject_path,
        )


def test_fix_normalizes_configuration_then_checks_it(tmp_path: Path) -> None:
    tach_path, policy_path, pyproject_path = _write_runner_fixture(tmp_path)

    runner.run(
        fix=True,
        tach_path=tach_path,
        policy_path=policy_path,
        pyproject_path=pyproject_path,
    )

    normalized_tach = tach_path.read_text(encoding="utf-8")
    assert normalized_tach.index('path = "apkg"') < normalized_tach.index(
        'path = "zpkg"'
    )
    assert 'known-first-party = [\n    "apkg",\n    "zpkg",\n]' in (
        pyproject_path.read_text(encoding="utf-8")
    )
    runner.run(
        fix=False,
        tach_path=tach_path,
        policy_path=policy_path,
        pyproject_path=pyproject_path,
    )


def test_check_is_non_mutating_and_rejects_unnormalized_configuration(
    tmp_path: Path,
) -> None:
    tach_path, policy_path, pyproject_path = _write_runner_fixture(tmp_path)
    original_tach = tach_path.read_text(encoding="utf-8")
    original_policy = policy_path.read_text(encoding="utf-8")
    original_pyproject = pyproject_path.read_text(encoding="utf-8")

    with pytest.raises(
        RuntimeError, match="Tach-managed configuration is not normalized"
    ):
        runner.run(
            fix=False,
            tach_path=tach_path,
            policy_path=policy_path,
            pyproject_path=pyproject_path,
        )

    assert tach_path.read_text(encoding="utf-8") == original_tach
    assert policy_path.read_text(encoding="utf-8") == original_policy
    assert pyproject_path.read_text(encoding="utf-8") == original_pyproject


def test_check_rejects_stale_ruff_configuration_without_mutating_it(
    tmp_path: Path,
) -> None:
    tach_path, policy_path, pyproject_path = _write_runner_fixture(tmp_path)
    runner.run(
        fix=True,
        tach_path=tach_path,
        policy_path=policy_path,
        pyproject_path=pyproject_path,
    )
    stale_pyproject = pyproject_path.read_text(encoding="utf-8").replace(
        '    "apkg",\n',
        "",
    )
    pyproject_path.write_text(stale_pyproject, encoding="utf-8")

    with assert_raises_msg(RuntimeError, "pyproject.toml"):
        runner.run(
            fix=False,
            tach_path=tach_path,
            policy_path=policy_path,
            pyproject_path=pyproject_path,
        )

    assert pyproject_path.read_text(encoding="utf-8") == stale_pyproject


def test_runner_requires_explicit_mode() -> None:
    with pytest.raises(SystemExit):
        runner.build_parser().parse_args([])


def test_external_lib_validation_uses_configured_package_source_root(
    tmp_path: Path,
) -> None:
    package = tmp_path / "src" / "pkg"
    package.mkdir(parents=True)
    package.joinpath("__init__.py").write_text("import pytest\n", encoding="utf-8")
    tach = parse_tach_config(_tach(module_path="pkg"))

    with pytest.raises(RuntimeError, match="blacklisted import 'pytest'"):
        validate_external_lib_whitelists(
            repo_root=tmp_path,
            tach=tach,
            module_specs=(
                ModulePolicy(
                    path="pkg",
                    external_lib_whitelist=frozenset(),
                ),
            ),
        )

    validate_external_lib_whitelists(
        repo_root=tmp_path,
        tach=tach,
        module_specs=(
            ModulePolicy(
                path="pkg",
                external_lib_whitelist=frozenset({"pytest"}),
            ),
        ),
    )


def test_external_lib_validation_supports_single_file_tach_module(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "src"
    source_root.mkdir()
    source_root.joinpath("standalone.py").write_text(
        "import pytest\n",
        encoding="utf-8",
    )
    tach = parse_tach_config(_tach(module_path="standalone"))

    with pytest.raises(RuntimeError, match="blacklisted import 'pytest'"):
        validate_external_lib_whitelists(
            repo_root=tmp_path,
            tach=tach,
            module_specs=(
                ModulePolicy(
                    path="standalone",
                    external_lib_whitelist=frozenset(),
                ),
            ),
        )
