# dev/tests/nox_tach_test/module_map_test.py
from __future__ import annotations

from dataclasses import replace

import pytest

from nox_tach.config import ModulePolicy, PolicyConfig, parse_policy_config
from nox_tach.module_map import render_module_map
from nox_tach.tach_config import parse_tach_config

_TACH = """\
source_roots = ["src", "dev"]
exact = true
root_module = "forbid"

[[modules]]
path = "worker"
depends_on = ["foundation"]

[[modules]]
path = "worker.jobs"
depends_on = ["foundation.helpers"]

[[modules]]
path = "foundation"
depends_on = []

[[modules]]
path = "foundation.helpers"
depends_on = []

[[modules]]
path = "specs"
depends_on = []

[[modules]]
path = "specs.helpers"
depends_on = []
"""

_POLICY = """\
[[modules]]
path = "foundation"
description = "Reusable foundation."
dependency_whitelist = []
external_lib_whitelist = []
collapse_references = true
collapse_references_except = ["worker.jobs"]

[[modules]]
path = "worker"
description = "Background | jobs."
parents_whitelist = ["specs.**"]

[[modules]]
path = "specs"
description = "Tests."
test_root = true
test_mirror_component_suffix = "_spec"

[[modules]]
path = "specs.helpers"
test_infra = true
dependency_whitelist = []
external_lib_whitelist = []
"""


def test_generic_map_uses_canonical_models_and_repository_metadata() -> None:
    rendered = render_module_map(
        tach=parse_tach_config(_TACH),
        config=parse_policy_config(_POLICY),
        pyproject_text="""\
[project]
name = "another-project"
[project.scripts]
zeta = "worker.zeta:main"
alpha = "worker.alpha:main"
[tool.fastapi]
entrypoint = "worker.http:app"
""",
    )

    assert rendered.startswith("# Generated another-project Module Map\n")
    assert rendered.index("`alpha`") < rendered.index("`zeta`")
    assert "| FastAPI | `application` | `worker.http:app` |" in rendered
    assert "| `worker` | production | Background \\| jobs. | `foundation` |" in rendered
    assert "Configured test roots: `1`" in rendered
    assert "| `specs.helpers` | — | dev-only |" in rendered
    assert "test root; mirror suffix: '_spec'" in rendered
    assert "test infrastructure" in rendered
    assert "collapse exclusions: worker.jobs" in rendered
    assert "parents whitelist: specs.**" in rendered
    assert "dependency whitelist: empty" in rendered

    # Canonical ordering and effective policy remain the parser's responsibility.
    reordered = replace(
        parse_policy_config(_POLICY),
        modules=tuple(reversed(parse_policy_config(_POLICY).modules)),
    )
    assert render_module_map(
        tach=parse_tach_config(_TACH),
        config=reordered,
        pyproject_text='[project]\nname = "plain"\n',
    ) == render_module_map(
        tach=parse_tach_config(_TACH),
        config=parse_policy_config(_POLICY),
        pyproject_text='[project]\nname = "plain"\n',
    )


def test_map_does_not_require_framework_or_entrypoints() -> None:
    rendered = render_module_map(
        tach=parse_tach_config(_TACH),
        config=parse_policy_config(_POLICY),
        pyproject_text='[project]\nname = "plain"\n',
        input_names=("graph.toml", "rules.toml", "project.toml"),
    )
    assert "| — | — | — |" in rendered
    assert "`graph.toml`, `rules.toml`, `project.toml`" in rendered
    assert "FastAPI" not in rendered
    assert "COMO" not in rendered


@pytest.mark.parametrize(
    ("config", "error"),
    [
        (PolicyConfig(modules=()), "Missing top-level module descriptions"),
        (
            PolicyConfig(modules=(ModulePolicy(path="stale", description="Old."),)),
            "Policy modules absent from tach.toml: stale",
        ),
    ],
)
def test_map_rejects_incomplete_or_stale_descriptions(
    config: PolicyConfig, error: str
) -> None:
    with pytest.raises(ValueError, match=error):
        render_module_map(
            tach=parse_tach_config(_TACH),
            config=config,
            pyproject_text='[project]\nname = "plain"\n',
        )


@pytest.mark.parametrize(
    "project",
    ["", '[project]\nname = ""', "[project]\nname = 1", 'project = "bad"'],
)
def test_map_rejects_invalid_project_metadata(project: str) -> None:
    with pytest.raises(ValueError, match=r"pyproject\.toml project"):
        render_module_map(
            tach=parse_tach_config(_TACH),
            config=parse_policy_config(_POLICY),
            pyproject_text=project,
        )
