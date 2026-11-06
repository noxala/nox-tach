# src/nox_tach/ruff_config.py
from __future__ import annotations

from datetime import datetime
import json
import re
import tomllib
from typing import cast
from zoneinfo import ZoneInfo

from nox_tach.tach_config import TachConfig

_RUFF_ISORT_HEADER_RE = re.compile(r"(?m)^\[tool\.ruff\.lint\.isort\][ \t]*(?:#.*)?$")
_TOML_TABLE_HEADER_RE = re.compile(r"(?m)^[ \t]*\[")
_KNOWN_FIRST_PARTY_RE = re.compile(
    r"(?ms)^(?P<prefix>[ \t]*known-first-party[ \t]*=[ \t]*)"
    r"\[(?P<body>.*?)\]"
)
_GENERATED_COMMENT_RE = re.compile(
    r"(?m)^(?P<indent>[ \t]*)# Generated from the top-level module roots in "
    r"tach\.toml by tach_como extensions"
    r"(?: on \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} (?:EST|EDT))?\.?[ \t]*\n\Z"
)
_GENERATED_COMMENT_PREFIX = (
    "# Generated from the top-level module roots in tach.toml by tach_como extensions"
)
_EASTERN_TIME = ZoneInfo("America/New_York")


def _table(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a TOML table")
    return cast(dict[str, object], value)


def _string_list(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a TOML array of strings")
    values = cast(list[object], value)
    if not all(isinstance(item, str) for item in values):
        raise ValueError(f"{field} must be a TOML array of strings")
    return tuple(cast(list[str], values))


def _ruff_isort_config(text: str) -> dict[str, object]:
    parsed = cast(dict[str, object], tomllib.loads(text))
    tool = _table(parsed.get("tool"), field="pyproject.toml tool")
    ruff = _table(tool.get("ruff"), field="pyproject.toml tool.ruff")
    lint = _table(ruff.get("lint"), field="pyproject.toml tool.ruff.lint")
    return _table(
        lint.get("isort"),
        field="pyproject.toml tool.ruff.lint.isort",
    )


def _ruff_isort_table_bounds(text: str) -> tuple[int, int]:
    headers = tuple(_RUFF_ISORT_HEADER_RE.finditer(text))
    if len(headers) != 1:
        raise ValueError(
            "pyproject.toml must contain exactly one [tool.ruff.lint.isort] table"
        )

    start = headers[0].end()
    next_header = _TOML_TABLE_HEADER_RE.search(text, start)
    end = len(text) if next_header is None else next_header.start()
    return start, end


def normalize_ruff_known_first_party(
    text: str,
    *,
    tach: TachConfig,
    generated_at: datetime | None = None,
) -> str:
    table_start, table_end = _ruff_isort_table_bounds(text)
    isort = _ruff_isort_config(text)
    known_third_party = frozenset(
        _string_list(
            isort.get("known-third-party", []),
            field="pyproject.toml tool.ruff.lint.isort.known-third-party",
        )
    )
    declared_module_roots = {module.path.partition(".")[0] for module in tach.modules}
    known_first_party = sorted(declared_module_roots - known_third_party)

    table_text = text[table_start:table_end]
    fields = tuple(_KNOWN_FIRST_PARTY_RE.finditer(table_text))
    if len(fields) != 1:
        raise ValueError(
            "pyproject.toml [tool.ruff.lint.isort] must contain exactly one "
            "known-first-party array"
        )

    field = fields[0]
    rendered_array = "[\n" + "".join(
        f"    {json.dumps(module_root)},\n" for module_root in known_first_party
    )
    rendered_array += "]"
    rendered_field = field.group("prefix") + rendered_array
    text_before_field = table_text[: field.start()]
    generated_comment = _GENERATED_COMMENT_RE.search(text_before_field)
    if field.group(0) == rendered_field and generated_comment is not None:
        return text

    if generated_at is None:
        generated_at = datetime.now(_EASTERN_TIME)
    if generated_at.tzinfo is None:
        raise ValueError("generated_at must have a timezone")
    timestamp = generated_at.astimezone(_EASTERN_TIME).strftime("%Y-%m-%d %H:%M:%S %Z")
    rendered_comment = f"{_GENERATED_COMMENT_PREFIX} on {timestamp}\n"
    if generated_comment is None:
        text_before_field += rendered_comment
    else:
        rendered_comment = generated_comment.group("indent") + rendered_comment
        text_before_field = (
            text_before_field[: generated_comment.start()] + rendered_comment
        )

    normalized_table = text_before_field + rendered_field + table_text[field.end() :]
    normalized = text[:table_start] + normalized_table + text[table_end:]
    tomllib.loads(normalized)
    return normalized
