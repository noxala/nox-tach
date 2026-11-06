# tests/test_ruff_config.py
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from nox_tach.ruff_config import (
    normalize_ruff_known_first_party,
)
from nox_tach.tach_config import parse_tach_config
from tests._helpers import assert_raises_msg


def test_normalize_ruff_known_first_party_uses_tach_roots_and_exceptions() -> None:
    tach = parse_tach_config(
        """\
source_roots = ["."]
exact = true
root_module = "forbid"

[[modules]]
path = "zpkg"
depends_on = []

[[modules]]
path = "apkg.child"
depends_on = []

[[modules]]
path = "apkg"
depends_on = []

[[modules]]
path = "alembic.migrations"
depends_on = []
"""
    )
    old_generated_comment = (
        "# Generated from the top-level module roots in tach.toml by tach_como "
        "extensions on 2025-01-01 00:00:00 EST"
    )
    pyproject = f"""\
[project]
name = "fixture"

[tool.ruff.lint.isort]
combine-as-imports = true
# This field is generated; this surrounding comment must survive.
{old_generated_comment}
known-first-party = ["stale"]
known-third-party = ["alembic"]

[tool.pytest.ini_options]
log_cli = true
"""

    generated_at = datetime(2026, 9, 2, 21, 59, 35, tzinfo=UTC)
    normalized = normalize_ruff_known_first_party(
        pyproject,
        tach=tach,
        generated_at=generated_at,
    )

    assert (
        "# Generated from the top-level module roots in tach.toml by tach_como "
        "extensions on 2026-09-02 17:59:35 EDT"
    ) in normalized
    assert "2025-01-01 00:00:00 EST" not in normalized
    assert 'known-first-party = [\n    "apkg",\n    "zpkg",\n]' in normalized
    assert 'known-third-party = ["alembic"]' in normalized
    assert "# This field is generated; this surrounding comment must survive." in (
        normalized
    )
    assert "[tool.pytest.ini_options]\nlog_cli = true" in normalized

    winter_normalized = normalize_ruff_known_first_party(
        pyproject,
        tach=tach,
        generated_at=datetime(2026, 1, 1, 17, tzinfo=UTC),
    )
    assert "extensions on 2026-01-01 12:00:00 EST" in winter_normalized
    assert (
        normalize_ruff_known_first_party(
            normalized,
            tach=tach,
            generated_at=datetime(2027, 1, 1, tzinfo=UTC),
        )
        == normalized
    )


@pytest.mark.parametrize(
    ("pyproject", "message"),
    [
        pytest.param(
            '[project]\nname = "fixture"\n',
            "pyproject.toml must contain exactly one [tool.ruff.lint.isort] table",
            id="missing-isort-table",
        ),
        pytest.param(
            "[tool.ruff.lint.isort]\nknown-third-party = []\n",
            "pyproject.toml [tool.ruff.lint.isort] must contain exactly one "
            "known-first-party array",
            id="missing-known-first-party",
        ),
    ],
)
def test_normalize_ruff_known_first_party_requires_managed_field(
    pyproject: str,
    message: str,
) -> None:
    tach = parse_tach_config(
        """\
source_roots = ["."]
exact = true
root_module = "forbid"

[[modules]]
path = "pkg"
depends_on = []
"""
    )

    with assert_raises_msg(ValueError, message):
        normalize_ruff_known_first_party(pyproject, tach=tach)
