# tests/test_normalization_sections.py
from __future__ import annotations

from pathlib import Path

from nox_tach.config import (
    ModulePolicy,
    PolicyConfig,
)
from nox_tach.normalization import (
    normalize_policy_text,
    normalize_tach_text,
)
from nox_tach.runner import run
from nox_tach.tach_config import parse_tach_config


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


def test_runner_normalization_is_idempotent(tmp_path: Path) -> None:
    tach_path = tmp_path / "tach.toml"
    policy_path = tmp_path / "nox_tach.toml"
    pyproject_path = tmp_path / "pyproject.toml"
    tach_path.write_text(
        """\
source_roots = ["."]
exact = true
root_module = "forbid"

[[modules]]
path = "tools"
depends_on = []

[[modules]]
path = "core"
depends_on = []
""",
        encoding="utf-8",
    )
    policy_path.write_text(
        """\
[[modules]]
path = "tools"
dev_only = true
""",
        encoding="utf-8",
    )
    pyproject_path.write_text(
        """\
[tool.ruff.lint.isort]
known-first-party = ["stale"]
known-third-party = []
""",
        encoding="utf-8",
    )

    run(
        fix=True,
        tach_path=tach_path,
        policy_path=policy_path,
        pyproject_path=pyproject_path,
    )
    first_tach = tach_path.read_text(encoding="utf-8")
    first_policy = policy_path.read_text(encoding="utf-8")
    first_pyproject = pyproject_path.read_text(encoding="utf-8")

    run(
        fix=True,
        tach_path=tach_path,
        policy_path=policy_path,
        pyproject_path=pyproject_path,
    )

    assert tach_path.read_text(encoding="utf-8") == first_tach
    assert policy_path.read_text(encoding="utf-8") == first_policy
    assert pyproject_path.read_text(encoding="utf-8") == first_pyproject
