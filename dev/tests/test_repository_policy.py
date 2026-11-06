# dev/tests/test_repository_policy.py
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from nox_tach.config import load_policy_config
from nox_tach.tach_config import parse_tach_config
from nox_tach.validators import (
    validate_dependency_whitelists,
    validate_mirrored_test_dependencies,
)

_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("consumer", "target", "mirrored"),
    [
        ("nox_tach.config", "nox_tach.runner", False),
        ("tests.nox_tach_test.config_test", "nox_tach.runner", True),
    ],
)
def test_repository_rejects_forbidden_dependency_after_sync(
    consumer: str, target: str, mirrored: bool
) -> None:
    tach = parse_tach_config((_ROOT / "tach.toml").read_text(encoding="utf-8"))
    config = load_policy_config(_ROOT / "nox_tach.toml")
    validate_dependency_whitelists(tach=tach, module_specs=config.modules)
    validate_mirrored_test_dependencies(tach=tach, config=config)
    mutated = replace(
        tach,
        modules=tuple(
            replace(module, depends_on=(*module.depends_on, target))
            if module.path == consumer
            else module
            for module in tach.modules
        ),
    )

    if mirrored:
        with pytest.raises(
            RuntimeError, match="outside that subject dependency cone"
        ) as error:
            validate_mirrored_test_dependencies(tach=mutated, config=config)
    else:
        # Internal restrictions survive syncing the new edge into tach.toml.
        with pytest.raises(RuntimeError, match="dependency_whitelist") as error:
            validate_dependency_whitelists(tach=mutated, module_specs=config.modules)
    assert consumer in str(error.value)
    assert target in str(error.value)


def test_native_tach_rejects_undeclared_internal_import(tmp_path: Path) -> None:
    for source in ("src", "dev"):
        shutil.copytree(
            _ROOT / source,
            tmp_path / source,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    shutil.copyfile(_ROOT / "tach.toml", tmp_path / "tach.toml")
    patterns = tmp_path / "src/nox_tach/patterns.py"
    with patterns.open("a", encoding="utf-8") as output:
        output.write("\nfrom nox_tach.runner import run\n")

    result = subprocess.run(
        [str(Path(sys.executable).with_name("tach")), "check"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode != 0
    assert "nox_tach.patterns" in result.stdout + result.stderr
    assert "cannot depend on 'nox_tach.runner'" in result.stdout + result.stderr
