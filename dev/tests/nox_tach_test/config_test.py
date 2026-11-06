# dev/tests/nox_tach_test/config_test.py
from __future__ import annotations

import pytest

from nox_tach.config import (
    ModulePolicy,
    PolicyConfig,
    TestRootSpec as PolicyTestRootSpec,
    parse_policy_config,
)
from tests._helpers import assert_raises_msg


def test_parse_policy_config_reads_module_policies() -> None:
    text = """\
[[modules]]
path = "core"
dependency_whitelist = []
external_lib_whitelist = []

[[modules]]
path = "specs"
test_root = true
test_mirror_component_suffix = "_spec"

[[modules]]
path = "specs.helpers"
test_infra = true
dependency_whitelist = ["server.**", "tools"]
parents_whitelist = ["specs", "tools.**"]
external_lib_whitelist = ["pytest"]
dev_only = true
collapse_references = true
collapse_references_except = ["zoop.zoop", "legacy.**"]
"""

    assert parse_policy_config(text) == PolicyConfig(
        modules=(
            ModulePolicy(
                path="core",
                dependency_whitelist=frozenset(),
                external_lib_whitelist=frozenset(),
            ),
            ModulePolicy(
                path="specs",
                test_root=True,
                test_mirror_component_suffix="_spec",
            ),
            ModulePolicy(
                path="specs.helpers",
                dependency_whitelist=frozenset({"server.**", "tools"}),
                parents_whitelist=frozenset({"specs", "tools.**"}),
                external_lib_whitelist=frozenset({"pytest"}),
                dev_only=True,
                test_infra=True,
                collapse_references=True,
                collapse_references_except=frozenset({"zoop.zoop", "legacy.**"}),
            ),
        )
    )


def test_parse_policy_config_distinguishes_absent_from_empty_whitelist() -> None:
    text = """\
[[modules]]
path = "app"
parents_whitelist = []
"""

    config = parse_policy_config(text)

    assert config.modules == (
        ModulePolicy(
            path="app",
            parents_whitelist=frozenset(),
        ),
    )


@pytest.mark.parametrize("value", ["1", "false", '""', '"  "'])
def test_description_requires_nonblank_text(value: str) -> None:
    with pytest.raises(ValueError, match="description must be a non-blank string"):
        parse_policy_config(f'[[modules]]\npath = "pkg"\ndescription = {value}\n')


def test_description_is_optional_documentation_metadata() -> None:
    assert parse_policy_config(
        '[[modules]]\npath = "pkg"\ndescription = "  Package purpose.  "\n'
    ).modules == (ModulePolicy(path="pkg", description="Package purpose."),)
    assert parse_policy_config('[[modules]]\npath = "pkg"\n').modules == (
        ModulePolicy(path="pkg"),
    )


def test_description_rejects_multiline_module_like_text() -> None:
    with pytest.raises(ValueError, match="description must be a single line"):
        parse_policy_config(
            '[[modules]]\npath = "pkg"\ndescription = """Purpose.\n[[modules]]\n"""\n'
        )


@pytest.mark.parametrize(
    ("text", "expected_message"),
    [
        pytest.param(
            'self_contained = ["core"]\n',
            "unknown top-level field",
            id="legacy_self_contained",
        ),
        pytest.param(
            """\
[[stdlib_only]]
path = "core"
module = "core"
""",
            "unknown top-level field",
            id="legacy_stdlib_only",
        ),
        pytest.param(
            """\
[[dependency_whitelist]]
module = "core"
whitelist = []
""",
            "unknown top-level field",
            id="legacy_dependency_whitelist",
        ),
        pytest.param(
            """\
[[modules]]
path = "core"
whitelist = []
""",
            "unknown field",
            id="unknown_module_field",
        ),
        pytest.param(
            """\
[[modules]]
""",
            ".path must be a non-blank string",
            id="missing_path",
        ),
        pytest.param(
            """\
[[modules]]
path = "core"
file_system_path = "core"
""",
            "unknown field",
            id="legacy_file_system_path",
        ),
        pytest.param(
            """\
[[modules]]
path = "core"
dependency_whitelist = []
dependency_blacklist = []
""",
            "may not specify both dependency_whitelist and dependency_blacklist",
            id="dependency_whitelist_and_blacklist_are_mutually_exclusive",
        ),
        pytest.param(
            """\
[[modules]]
path = "tools"
dev_only = "yes"
""",
            "dev_only must be a boolean",
            id="dev_only_must_be_boolean",
        ),
        pytest.param(
            """\
[[modules]]
path = "specs"
test_root = "yes"
""",
            "test_root must be a boolean",
            id="test_root_must_be_boolean",
        ),
        pytest.param(
            """\
[[modules]]
path = "specs"
test_infra = "yes"
""",
            "test_infra must be a boolean",
            id="test_infra_must_be_boolean",
        ),
        pytest.param(
            """\
[[modules]]
path = "core"
collapse_references = "yes"
""",
            "collapse_references must be a boolean",
            id="collapse_references_must_be_boolean",
        ),
        pytest.param(
            """\
[[modules]]
path = "core"
collapse_references_except = ["app"]
""",
            "collapse_references_except requires collapse_references = true",
            id="collapse_exceptions_requires_enabled_collapse",
        ),
        pytest.param(
            """\
[[modules]]
path = "core"
collapse_references = false
collapse_references_except = ["app"]
""",
            "collapse_references_except requires collapse_references = true",
            id="collapse_exceptions_rejects_explicit_false",
        ),
    ],
)
def test_parse_policy_config_rejects_invalid_shape(
    text: str,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        parse_policy_config(text)


@pytest.mark.parametrize(
    "legacy_key", ["collapse_references_blacklist", "collapse_references_exclude"]
)
@pytest.mark.parametrize("with_except", [False, True])
def test_parse_policy_config_rejects_legacy_collapse_key(
    legacy_key: str,
    with_except: bool,
) -> None:
    text = f"""\
[[modules]]
path = "core"
collapse_references = true
{legacy_key} = ["app"]
"""
    if with_except:
        text += 'collapse_references_except = ["app"]\n'

    with assert_raises_msg(
        ValueError, f"modules[0] has unknown field(s): {legacy_key!r}"
    ):
        parse_policy_config(text)


def test_parse_policy_config_preserves_absent_dev_only() -> None:
    config = parse_policy_config(
        """\
[[modules]]
path = "core"
"""
    )

    assert config.modules[0].dev_only is None
    assert config.is_dev_only("core") is False


def test_parse_policy_config_reads_explicit_dev_only_values() -> None:
    config = parse_policy_config(
        """\
[[modules]]
path = "tools"
dev_only = true

[[modules]]
path = "production"
dev_only = false
"""
    )

    assert config.modules[0].dev_only is True
    assert config.modules[1].dev_only is False
    assert config.is_dev_only("tools.child") is True
    assert config.is_dev_only("production") is False


def test_test_root_declares_mirror_rule_and_implies_dev_only() -> None:
    config = parse_policy_config(
        """\
[[modules]]
path = "specs"
test_root = true
test_mirror_component_suffix = "_spec"
"""
    )

    assert config.test_roots == (
        PolicyTestRootSpec(path="specs", mirror_component_suffix="_spec"),
    )
    assert config.test_root_for("specs.financial_spec") == config.test_roots[0]
    assert config.test_root_for("financial") is None
    assert config.is_dev_only("specs") is True
    assert config.is_dev_only("specs.financial_spec") is True


def test_test_root_allows_empty_mirror_suffix() -> None:
    config = parse_policy_config(
        """\
[[modules]]
path = "specs"
test_root = true
test_mirror_component_suffix = ""
"""
    )

    assert config.test_roots[0].mirror_component_suffix == ""


def test_test_infra_implies_dev_only_for_its_subtree() -> None:
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
    assert config.is_test_infra("specs.helpers.db") is True
    assert config.is_test_infra("specs.accounting_spec") is False
    assert config.is_dev_only("specs.helpers.db") is True


@pytest.mark.parametrize("field", ["test_root", "test_infra"])
def test_test_role_markers_reject_explicit_false(field: str) -> None:
    text = f"""\
[[modules]]
path = "specs"
{field} = false
"""

    with pytest.raises(ValueError, match="may only be true"):
        parse_policy_config(text)


def test_test_root_requires_mirror_suffix() -> None:
    with pytest.raises(ValueError, match="requires test_mirror_component_suffix"):
        parse_policy_config(
            """\
[[modules]]
path = "specs"
test_root = true
"""
        )


def test_test_mirror_suffix_requires_test_root() -> None:
    with pytest.raises(ValueError, match="requires test_root = true"):
        parse_policy_config(
            """\
[[modules]]
path = "specs"
test_mirror_component_suffix = "_spec"
"""
        )


def test_test_root_and_test_infra_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError, match="may not specify both test_root"):
        parse_policy_config(
            """\
[[modules]]
path = "specs"
test_root = true
test_infra = true
test_mirror_component_suffix = "_spec"
"""
        )


def test_nested_test_roots_are_rejected_order_independently() -> None:
    text = """\
[[modules]]
path = "specs.integration"
test_root = true
test_mirror_component_suffix = "_integration"

[[modules]]
path = "specs"
test_root = true
test_mirror_component_suffix = "_spec"
"""

    with pytest.raises(ValueError, match="Test roots must be disjoint"):
        parse_policy_config(text)


def test_test_infra_must_be_strict_descendant_of_test_root() -> None:
    with pytest.raises(ValueError, match="not a strict descendant"):
        parse_policy_config(
            """\
[[modules]]
path = "helpers"
test_infra = true
dependency_whitelist = []
external_lib_whitelist = []
"""
        )


def test_dev_only_false_is_rejected_below_test_root() -> None:
    text = """\
[[modules]]
path = "specs"
test_root = true
test_mirror_component_suffix = "_spec"

[[modules]]
path = "specs.accounting_spec"
dev_only = false
"""

    with assert_raises_msg(ValueError, "dev_only = false") as exc_info:
        parse_policy_config(text)

    assert "'specs'" in str(exc_info.value)


def test_dev_only_false_is_rejected_below_test_infra() -> None:
    text = """\
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
path = "specs.helpers.db"
dev_only = false
"""

    with assert_raises_msg(ValueError, "dev_only = false") as exc_info:
        parse_policy_config(text)

    assert "'specs.helpers'" in str(exc_info.value)


def test_test_roles_may_redundantly_declare_dev_only_true() -> None:
    parse_policy_config(
        """\
[[modules]]
path = "specs"
test_root = true
test_mirror_component_suffix = "_spec"
dev_only = true

[[modules]]
path = "specs.helpers"
test_infra = true
dependency_whitelist = []
external_lib_whitelist = []
dev_only = true
"""
    )


def test_parse_policy_config_defaults_collapse_references_to_false() -> None:
    config = parse_policy_config(
        """\
[[modules]]
path = "core"
"""
    )

    module = config.modules[0]
    assert module.collapse_references is False
    assert module.collapse_references_except == frozenset()


def test_parse_policy_config_accepts_collapse_exceptions_tach_patterns() -> None:
    config = parse_policy_config(
        """\
[[modules]]
path = "qb"
collapse_references = true
collapse_references_except = ["zoop.zoop", "legacy.*", "old.**"]
"""
    )

    module = config.modules[0]
    assert module.collapse_references is True
    assert module.collapse_references_except == frozenset(
        {"zoop.zoop", "legacy.*", "old.**"}
    )


def test_parse_policy_config_rejects_duplicate_module_path() -> None:
    text = """\
[[modules]]
path = "core"

[[modules]]
path = "core"
"""

    with pytest.raises(ValueError, match="duplicate policy for path 'core'"):
        parse_policy_config(text)


@pytest.mark.parametrize(
    "field",
    [
        pytest.param("dependency_whitelist", id="dependency_whitelist"),
        pytest.param("dependency_blacklist", id="dependency_blacklist"),
        pytest.param("parents_whitelist", id="parents"),
    ],
)
def test_parse_policy_config_accepts_tach_dependency_patterns(
    field: str,
) -> None:
    text = f"""\
[[modules]]
path = "client"
{field} = ["core", "financial.*", "models.**"]
"""

    config = parse_policy_config(text)
    module = config.modules[0]
    value = getattr(module, field)

    assert value == frozenset({"core", "financial.*", "models.**"})


@pytest.mark.parametrize(
    ("field", "pattern"),
    [
        pytest.param("dependency_whitelist", "core*", id="dependency_bad_glob"),
        pytest.param("dependency_whitelist", ".**", id="dependency_empty_root"),
        pytest.param("dependency_blacklist", "core*", id="blacklist_bad_glob"),
        pytest.param("parents_whitelist", "test*", id="parent_bad_glob"),
        pytest.param("parents_whitelist", "foo*bar.**", id="parent_nested_glob"),
    ],
)
def test_parse_policy_config_rejects_invalid_tach_patterns(
    field: str,
    pattern: str,
) -> None:
    text = f"""\
[[modules]]
path = "client"
{field} = ["{pattern}"]
"""

    with pytest.raises(ValueError, match="supports only exact Tach modules"):
        parse_policy_config(text)


def test_parse_policy_config_rejects_invalid_collapse_exceptions_pattern() -> None:
    text = """\
[[modules]]
path = "qb"
collapse_references = true
collapse_references_except = ["zoop*"]
"""

    with pytest.raises(ValueError, match="supports only exact Tach modules"):
        parse_policy_config(text)


def test_parse_policy_config_rejects_invalid_external_lib_name() -> None:
    text = """\
[[modules]]
path = "client"
external_lib_whitelist = ["pytest.*"]
"""

    with pytest.raises(ValueError, match="Invalid Python module name"):
        parse_policy_config(text)
