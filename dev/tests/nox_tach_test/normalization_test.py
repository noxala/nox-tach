# dev/tests/nox_tach_test/normalization_test.py
from __future__ import annotations

from nox_tach.config import (
    ModulePolicy,
    PolicyConfig,
    parse_policy_config,
)
from nox_tach.normalization import (
    collapse_dependency_references,
    normalize_policy_text,
    normalize_tach_text,
)
from nox_tach.tach_config import parse_tach_config
from tests._helpers import assert_raises_msg, tach_text


def test_normalization_preserves_module_description_metadata() -> None:
    text = (
        '[[modules]]\npath = "zpkg"\ndescription = "Package | purpose."\n'
        'dependency_whitelist = ["zpkg", "apkg"]\n'
        '\n[[modules]]\npath = "apkg"\ndescription = "Foundation."\n'
    )
    expected = parse_policy_config(text)
    normalized = normalize_policy_text(text)
    assert normalize_policy_text(normalized) == normalized
    assert {spec.path: spec for spec in parse_policy_config(normalized).modules} == {
        spec.path: spec for spec in expected.modules
    }


def test_normalize_tach_text_adds_stable_section_headers() -> None:
    text = """\
source_roots = ["."]
exact = true
root_module = "forbid"

# Keep this human-authored note.
[[modules]]
path = "tools.policy_engine"
depends_on = []

[[modules]]
path = "app"
depends_on = ["core"]

[[modules]]
path = "tools"
depends_on = []

[[modules]]
path = "core"
depends_on = []
"""
    tach = parse_tach_config(text)
    config = PolicyConfig(
        modules=(ModulePolicy(path="tools", dev_only=True),),
    )

    normalized = normalize_tach_text(text, tach=tach, config=config)
    normalized_twice = normalize_tach_text(
        normalized,
        tach=parse_tach_config(normalized),
        config=config,
    )

    assert normalized_twice == normalized
    assert (
        normalized.count("# --- Production modules: no first-party dependencies ---")
        == 1
    )
    assert (
        normalized.count("# --- Production modules: first-party dependencies ---") == 1
    )
    assert normalized.count("# --- Development-only modules ---") == 1
    assert normalized.index('path = "core"') < normalized.index('path = "app"')
    assert normalized.index('path = "app"') < normalized.index('path = "tools"')
    assert normalized.index('path = "tools"') < normalized.index(
        'path = "tools.policy_engine"'
    )
    assert "# Keep this human-authored note." in normalized


def test_normalize_policy_text_uses_effective_dev_only_status() -> None:
    text = """\
[[modules]]
path = "tools.policy_engine"
dependency_whitelist = []

[[modules]]
path = "core"
dependency_whitelist = []

[[modules]]
path = "tools"
dev_only = true
"""

    normalized = normalize_policy_text(text)
    normalized_twice = normalize_policy_text(normalized)

    assert normalized_twice == normalized
    assert normalized.count("# --- Production dependency policy ---") == 1
    assert normalized.count("# --- Development-only dependency policy ---") == 1
    assert normalized.index('path = "core"') < normalized.index('path = "tools"')
    assert normalized.index('path = "tools"') < normalized.index(
        'path = "tools.policy_engine"'
    )


def _core_collapse_specs(*, consumer: str) -> tuple[ModulePolicy, ...]:
    config = parse_policy_config(
        f"""\
[[modules]]
path = "core"
collapse_references = true
collapse_references_except = ["{consumer}"]
"""
    )
    return config.modules


def test_collapse_references_except_keeps_consumer_references_explicit() -> None:
    specs = _core_collapse_specs(consumer="test.core_test.lib")

    assert collapse_dependency_references(
        module_path="test.core_test.lib",
        dependencies=["core.lib", "core.lib.**"],
        module_specs=specs,
    ) == ["core.lib", "core.lib.**"]


def test_collapse_references_except_does_not_affect_other_consumers() -> None:
    specs = _core_collapse_specs(consumer="test.core_test.lib")

    assert collapse_dependency_references(
        module_path="test.core_test",
        dependencies=["core.lib", "core.json"],
        module_specs=specs,
    ) == ["core.**"]


def test_collapse_references_except_uses_tach_pattern_semantics() -> None:
    specs = _core_collapse_specs(consumer="test.core_test.**")

    assert collapse_dependency_references(
        module_path="test.core_test.lib.deep",
        dependencies=["core.lib"],
        module_specs=specs,
    ) == ["core.lib"]


def test_collapse_references_except_requires_enabled_collapse() -> None:
    with assert_raises_msg(
        ValueError,
        "modules[0].collapse_references_except requires collapse_references = true",
    ):
        parse_policy_config(
            """\
[[modules]]
path = "core"
collapse_references_except = ["test.core_test.lib"]
"""
        )


def test_normalize_policy_text_sorts_collapse_exceptions_idempotently() -> None:
    text = """\
[[modules]]
path = "core"
collapse_references = true
collapse_references_except = ["zeta.**", "app", "legacy.*"]
"""

    normalized = normalize_policy_text(text)

    assert 'collapse_references_except = ["app", "legacy.*", "zeta.**"]' in normalized
    assert normalize_policy_text(normalized) == normalized


def test_collapse_dependency_references_preserves_internal_references() -> None:
    specs = (ModulePolicy(path="core", collapse_references=True),)

    assert collapse_dependency_references(
        module_path="core.foo",
        dependencies=["core.lib", "models"],
        module_specs=specs,
    ) == ["core.lib", "models"]
    assert collapse_dependency_references(
        module_path="application",
        dependencies=["core.lib", "core.hashing", "models"],
        module_specs=specs,
    ) == ["core.**", "models"]


def test_normalize_tach_groups_zero_dep_prod_then_prod_then_dev() -> None:
    text = tach_text(
        ("dev.zero", []),
        ("zeta", ["alpha"]),
        ("alpha", []),
        ("beta", []),
        ("dev.work", ["alpha"]),
    )
    tach = parse_tach_config(text)
    config = PolicyConfig(
        modules=(ModulePolicy(path="dev", dev_only=True),),
    )

    rendered = normalize_tach_text(text, tach=tach, config=config)

    assert rendered.index('path = "alpha"') < rendered.index('path = "beta"')
    assert rendered.index('path = "beta"') < rendered.index('path = "zeta"')
    assert rendered.index('path = "zeta"') < rendered.index('path = "dev.work"')
    assert rendered.index('path = "dev.work"') < rendered.index('path = "dev.zero"')


def test_normalize_tach_como_groups_prod_then_effective_dev_only() -> None:
    text = """\
[[modules]]
path = "test.helpers"
test_infra = true
dependency_whitelist = []
external_lib_whitelist = []

[[modules]]
path = "zeta"

[[modules]]
path = "tools"
dev_only = true

[[modules]]
path = "alpha"

[[modules]]
path = "test"
test_root = true
test_mirror_component_suffix = "_test"
"""

    rendered = normalize_policy_text(text)

    assert rendered.index('path = "alpha"') < rendered.index('path = "zeta"')
    assert rendered.index('path = "zeta"') < rendered.index('path = "test"')
    assert rendered.index('path = "test"') < rendered.index('path = "test.helpers"')
    assert rendered.index('path = "test.helpers"') < rendered.index('path = "tools"')
