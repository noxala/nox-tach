# tests/test_test_role_tightening.py
from __future__ import annotations

import pytest

from nox_tach.config import parse_policy_config
from nox_tach.tach_config import parse_tach_config
from nox_tach.validators import (
    validate_test_infra_does_not_depend_on_focused_tests,
    validate_unique_mirrored_subjects,
)
from tests._helpers import assert_raises_msg


def _tach_text(*modules: tuple[str, list[str]]) -> str:
    body = "\n".join(
        f"""\
[[modules]]
path = {module_path!r}
depends_on = {dependencies!r}
"""
        for module_path, dependencies in modules
    )
    return f"""\
source_roots = ["."]
exact = true
root_module = "forbid"

{body}
"""


def test_test_infra_requires_explicit_dependency_surfaces() -> None:
    with assert_raises_msg(ValueError, "dependency_whitelist") as exc_info:
        parse_policy_config(
            """\
[[modules]]
path = "specs"
test_root = true
test_mirror_component_suffix = "_spec"

[[modules]]
path = "specs.helpers"
test_infra = true
"""
        )

    assert "external_lib_whitelist" in str(exc_info.value)


def test_test_infra_accepts_explicit_empty_dependency_surfaces() -> None:
    config = parse_policy_config(
        """\
[[modules]]
path = "specs"
test_root = true
test_mirror_component_suffix = "_spec"

[[modules]]
path = "specs.helpers"
test_infra = true
dependency_whitelist = []
external_lib_whitelist = []
"""
    )

    assert config.is_test_infra("specs.helpers") is True


def test_test_infra_cannot_depend_on_focused_test() -> None:
    config = parse_policy_config(
        """\
[[modules]]
path = "specs"
test_root = true
test_mirror_component_suffix = "_spec"

[[modules]]
path = "specs.helpers"
test_infra = true
dependency_whitelist = []
external_lib_whitelist = []
"""
    )
    tach = parse_tach_config(
        _tach_text(
            ("specs", []),
            ("specs.helpers", ["specs.billing_spec"]),
            ("specs.billing_spec", []),
        )
    )

    with pytest.raises(RuntimeError, match="may not depend on ordinary focused tests"):
        validate_test_infra_does_not_depend_on_focused_tests(
            tach=tach,
            config=config,
        )


def test_test_infra_may_depend_on_other_test_infra() -> None:
    config = parse_policy_config(
        """\
[[modules]]
path = "specs"
test_root = true
test_mirror_component_suffix = "_spec"

[[modules]]
path = "specs.helpers"
test_infra = true
dependency_whitelist = []
external_lib_whitelist = []

[[modules]]
path = "specs.database_helpers"
test_infra = true
dependency_whitelist = []
external_lib_whitelist = []
"""
    )
    tach = parse_tach_config(
        _tach_text(
            ("specs", []),
            ("specs.helpers", ["specs.database_helpers"]),
            ("specs.database_helpers", []),
        )
    )

    validate_test_infra_does_not_depend_on_focused_tests(tach=tach, config=config)


def test_one_test_root_cannot_map_two_modules_to_same_subject() -> None:
    config = parse_policy_config(
        """\
[[modules]]
path = "specs"
test_root = true
test_mirror_component_suffix = "_spec"
"""
    )
    tach = parse_tach_config(
        _tach_text(
            ("billing", []),
            ("specs.billing", ["billing"]),
            ("specs.billing_spec", ["billing"]),
        )
    )

    with pytest.raises(RuntimeError, match="multiple exact test modules"):
        validate_unique_mirrored_subjects(tach=tach, config=config)


def test_disjoint_test_roots_may_mirror_same_subject() -> None:
    config = parse_policy_config(
        """\
[[modules]]
path = "unit_specs"
test_root = true
test_mirror_component_suffix = "_spec"

[[modules]]
path = "integration_specs"
test_root = true
test_mirror_component_suffix = "_spec"
"""
    )
    tach = parse_tach_config(
        _tach_text(
            ("billing", []),
            ("unit_specs.billing_spec", ["billing"]),
            ("integration_specs.billing_spec", ["billing"]),
        )
    )

    validate_unique_mirrored_subjects(tach=tach, config=config)
