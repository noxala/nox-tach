# tests/test_policy.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from nox_tach.config import (
    ModulePolicy,
    PolicyConfig,
    TestRootSpec as PolicyTestRootSpec,
    parse_policy_config,
)
from nox_tach.imports import find_blacklisted_imports
from nox_tach.normalization import (
    collapse_dependency_references,
    normalize_policy_text,
    normalize_tach_text,
)
from nox_tach.tach_config import parse_tach_config
from nox_tach.validators import (
    mirrored_subject_module_path,
    validate_dependency_blacklists,
    validate_dependency_whitelist_blacklist_conflicts,
    validate_dependency_whitelists,
    validate_dev_only_dependencies,
    validate_mirrored_test_dependencies,
    validate_parents_whitelists,
    validate_policy_configuration,
    validate_policy_modules_are_tach_modules,
    validate_tach_pattern_references_are_tach_modules,
    validate_test_dependencies,
    validate_whitelist_policies_only_narrow,
)


def _tach_text(*modules: tuple[str, list[str]]) -> str:
    body = "\n".join(
        f"""\
[[modules]]
path = {json.dumps(module_path)}
depends_on = {json.dumps(dependencies)}
"""
        for module_path, dependencies in modules
    )
    return f"""\
source_roots = ["."]
exact = true
root_module = "forbid"

{body}
"""


def _module_spec(
    path: str,
    *,
    dependency_whitelist: frozenset[str] | None = None,
    dependency_blacklist: frozenset[str] | None = None,
    parents_whitelist: frozenset[str] | None = None,
    dev_only: bool | None = None,
    collapse_references: bool = False,
    collapse_references_blacklist: frozenset[str] = frozenset(),
) -> ModulePolicy:
    return ModulePolicy(
        path=path,
        dependency_whitelist=dependency_whitelist,
        dependency_blacklist=dependency_blacklist,
        parents_whitelist=parents_whitelist,
        dev_only=dev_only,
        collapse_references=collapse_references,
        collapse_references_blacklist=collapse_references_blacklist,
    )


def _test_config() -> PolicyConfig:
    return parse_policy_config(
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


def test_collapse_dependency_references_preserves_internal_references() -> None:
    specs = (_module_spec("core", collapse_references=True),)

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


@pytest.mark.parametrize(
    ("module_path", "expected"),
    [
        pytest.param(
            "specs.financial_spec.loan_spec",
            "financial.loan",
            id="configured_suffix",
        ),
        pytest.param(
            "specs.financial.loan",
            "financial.loan",
            id="natural_component_name",
        ),
        pytest.param(
            "specs.financial_spec.loan_spec.amortization_spec",
            "financial.loan.amortization",
            id="suffix_removed_from_each_component",
        ),
    ],
)
def test_mirrored_subject_module_path(module_path: str, expected: str) -> None:
    root = PolicyTestRootSpec(path="specs", mirror_component_suffix="_spec")
    assert mirrored_subject_module_path(module_path, test_root=root) == expected


def test_test_dependency_policy_allows_same_root_and_test_infra() -> None:
    config = _test_config()
    tach = parse_tach_config(
        _tach_text(
            ("specs.financial_spec", ["specs.other_spec", "specs.helpers"]),
            ("specs.other_spec", []),
            ("specs.helpers", []),
        )
    )

    validate_test_dependencies(tach=tach, config=config)


def test_test_dependency_policy_rejects_external_focused_test_consumer() -> None:
    config = _test_config()
    tach = parse_tach_config(
        _tach_text(
            ("diagnostics", ["specs.financial_spec"]),
            ("specs.financial_spec", []),
        )
    )

    with pytest.raises(RuntimeError, match="test-dependency policy violated"):
        validate_test_dependencies(tach=tach, config=config)


def test_mirrored_test_policy_accepts_subject_transitive_cone() -> None:
    config = _test_config()
    tach = parse_tach_config(
        _tach_text(
            ("core", []),
            ("financial.primitives", ["core"]),
            ("financial.loan", ["financial.primitives"]),
            ("specs.financial_spec.loan_spec", ["core", "specs.helpers"]),
            ("specs.helpers", []),
        )
    )

    validate_mirrored_test_dependencies(tach=tach, config=config)


def test_mirrored_test_policy_rejects_dependency_outside_subject_cone() -> None:
    config = _test_config()
    tach = parse_tach_config(
        _tach_text(
            ("core", []),
            ("payments", []),
            ("financial.loan", ["core"]),
            ("specs.financial_spec.loan_spec", ["payments"]),
        )
    )

    with pytest.raises(RuntimeError, match="outside that subject dependency cone"):
        validate_mirrored_test_dependencies(tach=tach, config=config)


def test_non_dev_module_cannot_depend_on_dev_only_module() -> None:
    tach = parse_tach_config(
        _tach_text(
            ("app", ["diagnostics"]),
            ("diagnostics", []),
        )
    )
    config = PolicyConfig(
        modules=(_module_spec("diagnostics", dev_only=True),),
    )

    with pytest.raises(RuntimeError, match="dev-only dependency policy violated"):
        validate_dev_only_dependencies(tach=tach, config=config)


def test_dependency_whitelist_implicitly_allows_its_own_subtree() -> None:
    tach = parse_tach_config(
        _tach_text(
            ("core", ["core.lib"]),
            ("core.lib", ["core.lib.deep"]),
            ("core.lib.deep", []),
        )
    )
    validate_dependency_whitelists(
        tach=tach,
        module_specs=(_module_spec("core", dependency_whitelist=frozenset()),),
    )


def test_child_dependency_whitelist_establishes_narrower_self_subtree() -> None:
    tach = parse_tach_config(
        _tach_text(
            ("core", ["core.hashing"]),
            ("core.hashing", []),
            ("core.lib", ["core.hashing"]),
        )
    )
    specs = (
        _module_spec("core", dependency_whitelist=frozenset()),
        _module_spec("core.lib", dependency_whitelist=frozenset()),
    )

    with pytest.raises(RuntimeError, match="dependency_whitelist policy violated"):
        validate_dependency_whitelists(tach=tach, module_specs=specs)


def test_child_whitelist_can_retain_parent_subtree_access() -> None:
    tach = parse_tach_config(
        _tach_text(
            ("core", ["core.hashing"]),
            ("core.hashing", []),
            ("core.lib", ["core.hashing"]),
        )
    )
    specs = (
        _module_spec("core", dependency_whitelist=frozenset()),
        _module_spec(
            "core.lib",
            dependency_whitelist=frozenset({"core.hashing"}),
        ),
    )

    validate_whitelist_policies_only_narrow(module_specs=specs)
    validate_dependency_whitelists(tach=tach, module_specs=specs)


def test_child_dependency_whitelist_cannot_retain_permission_parent_lacks() -> None:
    specs = (
        _module_spec("core", dependency_whitelist=frozenset()),
        _module_spec(
            "core.lib",
            dependency_whitelist=frozenset({"qb"}),
        ),
    )

    with pytest.raises(RuntimeError, match="whitelist narrowing policy violated"):
        validate_whitelist_policies_only_narrow(module_specs=specs)


def test_child_parents_whitelist_establishes_narrower_self_subtree() -> None:
    tach = parse_tach_config(
        _tach_text(
            ("core.hashing", ["core.lib"]),
            ("core.lib", []),
        )
    )
    specs = (
        _module_spec("core", parents_whitelist=frozenset()),
        _module_spec("core.lib", parents_whitelist=frozenset()),
    )

    with pytest.raises(RuntimeError, match="parents_whitelist policy violated"):
        validate_parents_whitelists(tach=tach, module_specs=specs)


def test_child_parents_whitelist_can_explicitly_retain_parent_subtree_caller() -> None:
    tach = parse_tach_config(
        _tach_text(
            ("core.hashing", ["core.lib"]),
            ("core.lib", []),
        )
    )
    specs = (
        _module_spec("core", parents_whitelist=frozenset()),
        _module_spec(
            "core.lib",
            parents_whitelist=frozenset({"core.hashing"}),
        ),
    )

    validate_whitelist_policies_only_narrow(module_specs=specs)
    validate_parents_whitelists(tach=tach, module_specs=specs)


def test_dependency_blacklist_is_inherited_and_transitive() -> None:
    tach = parse_tach_config(
        _tach_text(
            ("app", ["bridge"]),
            ("app.child", []),
            ("bridge", ["tools"]),
            ("tools", []),
        )
    )
    specs = (
        _module_spec(
            "app",
            dependency_blacklist=frozenset({"tools", "tools.**"}),
        ),
    )

    with pytest.raises(RuntimeError, match="reaches blacklisted module 'tools'"):
        validate_dependency_blacklists(tach=tach, module_specs=specs)


def test_descendant_whitelist_cannot_reopen_inherited_blacklist() -> None:
    specs = (
        _module_spec(
            "financial",
            dependency_blacklist=frozenset({"tools.**"}),
        ),
        _module_spec(
            "financial.loan",
            dependency_whitelist=frozenset({"tools.helper"}),
        ),
    )

    with pytest.raises(RuntimeError, match="ancestor blacklists cannot be reopened"):
        validate_dependency_whitelist_blacklist_conflicts(module_specs=specs)


def test_policy_paths_and_pattern_roots_must_be_exact_tach_modules() -> None:
    tach = parse_tach_config(_tach_text(("core", []), ("client", [])))

    with pytest.raises(RuntimeError, match="Missing modules: 'missing'"):
        validate_policy_modules_are_tach_modules(
            tach=tach,
            module_specs=(_module_spec("missing"),),
        )

    with pytest.raises(RuntimeError, match=r"not an exact \[\[modules\]\] path"):
        validate_tach_pattern_references_are_tach_modules(
            tach=tach,
            module_specs=(
                _module_spec(
                    "client",
                    dependency_whitelist=frozenset({"missing.**"}),
                ),
            ),
        )


def test_tach_policy_configuration_runs_all_configuration_checks() -> None:
    with pytest.raises(RuntimeError, match="dependency_blacklist configuration"):
        validate_policy_configuration(
            module_specs=(
                _module_spec(
                    "app",
                    dependency_blacklist=frozenset({"tools.**"}),
                ),
            )
        )


def test_normalize_tach_groups_zero_dep_prod_then_prod_then_dev() -> None:
    text = _tach_text(
        ("dev.zero", []),
        ("zeta", ["alpha"]),
        ("alpha", []),
        ("beta", []),
        ("dev.work", ["alpha"]),
    )
    tach = parse_tach_config(text)
    config = PolicyConfig(
        modules=(_module_spec("dev", dev_only=True),),
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
