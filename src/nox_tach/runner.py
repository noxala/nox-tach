# src/nox_tach/runner.py
from __future__ import annotations

import argparse
from collections.abc import Sequence
import difflib
import os
from pathlib import Path
import shlex
import sys
from typing import cast

from nox_tach.config import (
    PolicyConfig,
    parse_policy_config,
)
from nox_tach.imports import validate_external_lib_whitelists
from nox_tach.module_map import render_module_map
from nox_tach.normalization import (
    normalize_policy_text,
    normalize_tach_text,
)
from nox_tach.ruff_config import normalize_ruff_known_first_party
from nox_tach.tach_config import (
    TachConfig,
    parse_tach_config,
    top_level_python_packages,
)
from nox_tach.validators import (
    validate_dependency_blacklists,
    validate_dependency_whitelists,
    validate_dev_only_dependencies,
    validate_mirrored_test_dependencies,
    validate_parents_whitelists,
    validate_policy_configuration,
    validate_policy_modules_are_tach_modules,
    validate_required_tach_settings,
    validate_tach_pattern_references_are_tach_modules,
    validate_test_dependencies,
    validate_test_infra_does_not_depend_on_focused_tests,
    validate_unique_mirrored_subjects,
)

_DEFAULT_TACH_PATH = Path("tach.toml")
_DEFAULT_POLICY_PATH = Path("nox_tach.toml")
_DEFAULT_PYPROJECT_PATH = Path("pyproject.toml")
_DEFAULT_OUTPUT_PATH = Path("docs/generated/MODULE_MAP.md")


def validate_top_level_packages(
    *,
    repo_root: Path,
    tach: TachConfig,
) -> None:
    package_names = top_level_python_packages(
        repo_root=repo_root,
        source_roots=tach.source_roots,
    )
    missing_packages = sorted(package_names - tach.module_paths)
    if len(missing_packages) == 0:
        return

    formatted_missing = ", ".join(repr(name) for name in missing_packages)
    raise RuntimeError(
        "Every top-level Python package under Tach source_roots must be declared as "
        "an exact [[modules]] path in tach.toml. "
        f"Missing top-level packages: {formatted_missing}"
    )


def _validate_declared_topology(
    *,
    repo_root: Path,
    tach: TachConfig,
    config: PolicyConfig,
) -> None:
    validate_policy_configuration(module_specs=config.modules)
    validate_required_tach_settings(tach=tach)
    validate_policy_modules_are_tach_modules(
        tach=tach,
        module_specs=config.modules,
    )
    validate_tach_pattern_references_are_tach_modules(
        tach=tach,
        module_specs=config.modules,
    )
    validate_top_level_packages(repo_root=repo_root, tach=tach)


def _validate_dependency_policy(
    *,
    repo_root: Path,
    tach: TachConfig,
    config: PolicyConfig,
) -> None:
    validate_dev_only_dependencies(tach=tach, config=config)
    validate_external_lib_whitelists(
        repo_root=repo_root,
        tach=tach,
        module_specs=config.modules,
    )
    validate_test_dependencies(tach=tach, config=config)
    validate_test_infra_does_not_depend_on_focused_tests(tach=tach, config=config)
    validate_unique_mirrored_subjects(tach=tach, config=config)
    validate_mirrored_test_dependencies(tach=tach, config=config)
    validate_dependency_whitelists(
        tach=tach,
        module_specs=config.modules,
    )
    validate_dependency_blacklists(
        tach=tach,
        module_specs=config.modules,
    )
    validate_parents_whitelists(
        tach=tach,
        module_specs=config.modules,
    )


def _load_configs(
    *,
    tach_path: Path,
    policy_path: Path,
) -> tuple[str, TachConfig, str, PolicyConfig]:
    tach_text = tach_path.read_text(encoding="utf-8")
    tach = parse_tach_config(tach_text)
    policy_text = policy_path.read_text(encoding="utf-8")
    config = parse_policy_config(policy_text)
    return tach_text, tach, policy_text, config


def _normalized_texts(
    *,
    tach_text: str,
    tach: TachConfig,
    policy_text: str,
    config: PolicyConfig,
    pyproject_text: str,
) -> tuple[str, str, str]:
    return (
        normalize_tach_text(tach_text, tach=tach, config=config),
        normalize_policy_text(policy_text),
        normalize_ruff_known_first_party(pyproject_text, tach=tach),
    )


def _validate_normalized(
    *,
    tach_path: Path,
    policy_path: Path,
    pyproject_path: Path,
    tach_text: str,
    normalized_tach_text: str,
    policy_text: str,
    normalized_policy_text: str,
    pyproject_text: str,
    normalized_pyproject_text: str,
) -> None:
    unnormalized: list[str] = []
    if tach_text != normalized_tach_text:
        unnormalized.append(str(tach_path))
    if policy_text != normalized_policy_text:
        unnormalized.append(str(policy_path))
    if pyproject_text != normalized_pyproject_text:
        unnormalized.append(str(pyproject_path))
    if len(unnormalized) == 0:
        return

    formatted_paths = ", ".join(unnormalized)
    command = shlex.join(
        [
            "nox-tach",
            "--fix",
            "--tach-path",
            str(tach_path),
            "--policy-path",
            str(policy_path),
            "--pyproject-path",
            str(pyproject_path),
        ]
    )
    raise RuntimeError(
        f"Tach-managed configuration is not normalized: {formatted_paths}. "
        f"Run `{command}`."
    )


def _check(*, tach_path: Path, policy_path: Path, pyproject_path: Path) -> None:
    tach_text, tach, policy_text, config = _load_configs(
        tach_path=tach_path,
        policy_path=policy_path,
    )
    pyproject_text = pyproject_path.read_text(encoding="utf-8")
    repo_root = tach_path.resolve().parent

    _validate_declared_topology(repo_root=repo_root, tach=tach, config=config)
    _validate_dependency_policy(repo_root=repo_root, tach=tach, config=config)
    (
        normalized_tach_text,
        normalized_policy_text,
        normalized_pyproject_text,
    ) = _normalized_texts(
        tach_text=tach_text,
        tach=tach,
        policy_text=policy_text,
        config=config,
        pyproject_text=pyproject_text,
    )
    _validate_normalized(
        tach_path=tach_path,
        policy_path=policy_path,
        pyproject_path=pyproject_path,
        tach_text=tach_text,
        normalized_tach_text=normalized_tach_text,
        policy_text=policy_text,
        normalized_policy_text=normalized_policy_text,
        pyproject_text=pyproject_text,
        normalized_pyproject_text=normalized_pyproject_text,
    )


def run(
    *,
    fix: bool,
    tach_path: Path = _DEFAULT_TACH_PATH,
    policy_path: Path = _DEFAULT_POLICY_PATH,
    pyproject_path: Path = _DEFAULT_PYPROJECT_PATH,
) -> None:
    if not fix:
        _check(
            tach_path=tach_path,
            policy_path=policy_path,
            pyproject_path=pyproject_path,
        )
        return

    tach_text, tach, policy_text, config = _load_configs(
        tach_path=tach_path,
        policy_path=policy_path,
    )
    pyproject_text = pyproject_path.read_text(encoding="utf-8")
    repo_root = tach_path.resolve().parent

    # Fixing never creates architectural boundaries. Validate the declared topology
    # before writing anything so a missing top-level module remains a conscious edit.
    _validate_declared_topology(repo_root=repo_root, tach=tach, config=config)
    (
        normalized_tach_text,
        normalized_policy_text,
        normalized_pyproject_text,
    ) = _normalized_texts(
        tach_text=tach_text,
        tach=tach,
        policy_text=policy_text,
        config=config,
        pyproject_text=pyproject_text,
    )
    tach_path.write_text(normalized_tach_text, encoding="utf-8")
    policy_path.write_text(normalized_policy_text, encoding="utf-8")
    pyproject_path.write_text(normalized_pyproject_text, encoding="utf-8")

    # --fix is a strict superset of --check: validate the files after fixing them.
    _check(
        tach_path=tach_path,
        policy_path=policy_path,
        pyproject_path=pyproject_path,
    )


def run_docs(
    *,
    check: bool,
    tach_path: Path = _DEFAULT_TACH_PATH,
    policy_path: Path = _DEFAULT_POLICY_PATH,
    pyproject_path: Path = _DEFAULT_PYPROJECT_PATH,
    output_path: Path = _DEFAULT_OUTPUT_PATH,
) -> None:
    repo_root = tach_path.resolve().parent
    output_path = (repo_root / output_path).resolve()
    inputs = (tach_path, policy_path, pyproject_path)
    if output_path in {path.resolve() for path in inputs}:
        raise ValueError("The module-map output must not overwrite an input file")

    _, tach, _, config = _load_configs(tach_path=tach_path, policy_path=policy_path)
    expected = render_module_map(
        tach=tach,
        config=config,
        pyproject_text=pyproject_path.read_text(encoding="utf-8"),
        input_names=tuple(
            os.path.relpath(path.resolve(), repo_root) for path in inputs
        ),
    )
    if not check:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(expected, encoding="utf-8")
        sys.stdout.write(f"Wrote {output_path}\n")
        return

    actual = output_path.read_text(encoding="utf-8") if output_path.is_file() else ""
    if actual == expected:
        return
    diff = difflib.unified_diff(
        actual.splitlines(),
        expected.splitlines(),
        fromfile=str(output_path),
        tofile=f"{output_path} (generated)",
        lineterm="",
    )
    sys.stdout.write("\n".join(diff) + "\n")
    command = shlex.join(
        [
            "nox-tach",
            "docs",
            "--tach-path",
            str(tach_path),
            "--policy-path",
            str(policy_path),
            "--pyproject-path",
            str(pyproject_path),
            "--output",
            str(output_path),
        ]
    )
    raise RuntimeError(f"Generated module map is missing or stale. Run `{command}`.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate or fix Tach policy.",
        epilog=(
            "Generate a module map with 'nox-tach docs'; "
            "use 'nox-tach docs --help' for options."
        ),
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--fix",
        action="store_true",
        help="Normalize Tach-managed configuration, then validate it.",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="Validate Tach-managed configuration without modifying files.",
    )
    _add_config_arguments(parser)
    return parser


def _add_config_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--tach-path",
        type=Path,
        default=_DEFAULT_TACH_PATH,
        help="Path to tach.toml.",
    )
    parser.add_argument(
        "--policy-path",
        type=Path,
        default=_DEFAULT_POLICY_PATH,
        help="Path to the extension policy TOML.",
    )
    parser.add_argument(
        "--pyproject-path",
        type=Path,
        default=_DEFAULT_PYPROJECT_PATH,
        help="Path to pyproject.toml.",
    )


def _build_docs_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nox-tach docs", description="Generate or check a Markdown module map."
    )
    parser.add_argument("--check", action="store_true", help="Check without writing.")
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT_PATH,
        help="Output path relative to the Tach file's parent (or an absolute path).",
    )
    _add_config_arguments(parser)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "docs":
        args = _build_docs_parser().parse_args(arguments[1:])
        run_docs(
            check=cast(bool, args.check),
            tach_path=cast(Path, args.tach_path),
            policy_path=cast(Path, args.policy_path),
            pyproject_path=cast(Path, args.pyproject_path),
            output_path=cast(Path, args.output),
        )
        return
    args = build_parser().parse_args(arguments)
    run(
        fix=cast(bool, args.fix),
        tach_path=cast(Path, args.tach_path),
        policy_path=cast(Path, args.policy_path),
        pyproject_path=cast(Path, args.pyproject_path),
    )
