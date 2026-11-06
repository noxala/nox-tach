# dev/tests/test_normalization_integration.py
from __future__ import annotations

from pathlib import Path

from nox_tach.runner import run


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
