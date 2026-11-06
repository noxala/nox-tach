# tests/test_collapse_exclude.py
from __future__ import annotations

from nox_tach.config import (
    ModulePolicy,
    parse_policy_config,
)
from nox_tach.normalization import collapse_dependency_references
from tests._helpers import assert_raises_msg


def _core_collapse_specs(*, exclude: str) -> tuple[ModulePolicy, ...]:
    config = parse_policy_config(
        f"""\
[[modules]]
path = "core"
collapse_references = true
collapse_references_exclude = ["{exclude}"]
"""
    )
    return config.modules


def test_collapse_references_exclude_keeps_consumer_references_explicit() -> None:
    specs = _core_collapse_specs(exclude="test.core_test.lib")

    assert collapse_dependency_references(
        module_path="test.core_test.lib",
        dependencies=["core.lib", "core.lib.**"],
        module_specs=specs,
    ) == ["core.lib", "core.lib.**"]


def test_collapse_references_exclude_does_not_affect_other_consumers() -> None:
    specs = _core_collapse_specs(exclude="test.core_test.lib")

    assert collapse_dependency_references(
        module_path="test.core_test",
        dependencies=["core.lib", "core.json"],
        module_specs=specs,
    ) == ["core.**"]


def test_collapse_references_exclude_uses_tach_pattern_semantics() -> None:
    specs = _core_collapse_specs(exclude="test.core_test.**")

    assert collapse_dependency_references(
        module_path="test.core_test.lib.deep",
        dependencies=["core.lib"],
        module_specs=specs,
    ) == ["core.lib"]


def test_collapse_references_exclude_requires_enabled_collapse() -> None:
    with assert_raises_msg(
        ValueError,
        "modules[0].collapse_references_exclude requires collapse_references = true",
    ):
        parse_policy_config(
            """\
[[modules]]
path = "core"
collapse_references_exclude = ["test.core_test.lib"]
"""
        )
