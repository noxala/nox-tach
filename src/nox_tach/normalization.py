# src/nox_tach/normalization.py
from __future__ import annotations

import json
import re
import tomllib
from typing import cast

from nox_tach.config import (
    ModulePolicy,
    PolicyConfig,
    parse_policy_config,
)
from nox_tach.patterns import (
    module_matches_tach_patterns,
    module_within_root,
)
from nox_tach.tach_config import TachConfig, parse_tach_config

_MODULE_HEADER_RE = re.compile(r"(?m)^\[\[modules\s*\]\]")
_DEPENDS_ON_RE = re.compile(
    r"(?m)^depends_on\s*=\s*\[(.*?)\]",
    flags=re.DOTALL,
)
_LIST_FIELD_NAMES = (
    "dependency_whitelist",
    "dependency_blacklist",
    "parents_whitelist",
    "external_lib_whitelist",
    "collapse_references_blacklist",
)
_TACH_ZERO_DEPENDENCY_PRODUCTION_HEADER = (
    "# --- Production modules: no first-party dependencies ---"
)
_TACH_PRODUCTION_HEADER = "# --- Production modules: first-party dependencies ---"
_TACH_DEV_ONLY_HEADER = "# --- Development-only modules ---"
_POLICY_PRODUCTION_HEADER = "# --- Production dependency policy ---"
_POLICY_DEV_ONLY_HEADER = "# --- Development-only dependency policy ---"
_GENERATED_SECTION_HEADERS = frozenset(
    {
        _TACH_ZERO_DEPENDENCY_PRODUCTION_HEADER,
        _TACH_PRODUCTION_HEADER,
        _TACH_DEV_ONLY_HEADER,
        _POLICY_PRODUCTION_HEADER,
        _POLICY_DEV_ONLY_HEADER,
    }
)


def collapse_references_for_spec(
    *,
    module_path: str,
    dependencies: list[str],
    spec: ModulePolicy,
) -> list[str]:
    if not spec.collapse_references:
        return dependencies
    if module_within_root(module_path, spec.path):
        return dependencies
    if module_matches_tach_patterns(
        module_path,
        spec.collapse_references_blacklist,
    ):
        return dependencies

    has_exact_reference = spec.path in dependencies
    has_descendant_reference = any(
        dependency.startswith(f"{spec.path}.") for dependency in dependencies
    )
    if not has_exact_reference and not has_descendant_reference:
        return dependencies

    other_dependencies = [
        dependency
        for dependency in dependencies
        if not module_within_root(dependency, spec.path)
    ]
    collapsed_references: list[str] = []
    if has_exact_reference:
        collapsed_references.append(spec.path)
    if has_descendant_reference:
        collapsed_references.append(f"{spec.path}.**")
    return [*collapsed_references, *other_dependencies]


def collapse_dependency_references(
    *,
    module_path: str,
    dependencies: list[str],
    module_specs: tuple[ModulePolicy, ...],
) -> list[str]:
    collapsed = dependencies
    collapse_specs = sorted(
        (spec for spec in module_specs if spec.collapse_references),
        key=lambda spec: len(spec.path.split(".")),
    )
    for spec in collapse_specs:
        collapsed = collapse_references_for_spec(
            module_path=module_path,
            dependencies=collapsed,
            spec=spec,
        )
    return collapsed


def normalize_depends_on(
    block: str,
    *,
    module_specs: tuple[ModulePolicy, ...],
) -> str:
    parsed = cast(dict[str, object], tomllib.loads(block))
    modules = cast(list[dict[str, object]], parsed["modules"])
    module = modules[0]
    module_path = cast(str, module["path"])
    dependencies = cast(list[str], module["depends_on"])
    dependencies = collapse_dependency_references(
        module_path=module_path,
        dependencies=dependencies,
        module_specs=module_specs,
    )
    dependencies = sorted(set(dependencies))

    formatted = ", ".join(json.dumps(dependency) for dependency in dependencies)
    replacement = f"depends_on = [{formatted}]"
    updated_block, replacement_count = _DEPENDS_ON_RE.subn(
        replacement,
        block,
        count=1,
    )
    if replacement_count != 1:
        raise RuntimeError(
            f"Expected exactly one depends_on entry in module "
            f"{module_path!r}, got {replacement_count}"
        )
    return updated_block


def _block_identity(block: str) -> tuple[str, int]:
    parsed = cast(dict[str, object], tomllib.loads(block))
    modules = cast(list[dict[str, object]], parsed["modules"])
    module = modules[0]
    path = cast(str, module["path"])
    dependencies = cast(list[str], module.get("depends_on", []))
    return path, len(dependencies)


def _block_path(block: str) -> str:
    return _block_identity(block)[0]


def _tach_groups(
    blocks: list[str],
    *,
    config: PolicyConfig,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    zero_dependency_production: list[str] = []
    production: list[str] = []
    dev_only: list[str] = []

    for block in blocks:
        path, dependency_count = _block_identity(block)
        if config.is_dev_only(path):
            dev_only.append(block)
        elif dependency_count == 0:
            zero_dependency_production.append(block)
        else:
            production.append(block)

    zero_dependency_production.sort(key=_block_path)
    production.sort(key=_block_path)
    dev_only.sort(key=_block_path)
    return (
        tuple(zero_dependency_production),
        tuple(production),
        tuple(dev_only),
    )


def _strip_generated_section_headers(text: str) -> str:
    lines = [
        line for line in text.splitlines() if line not in _GENERATED_SECTION_HEADERS
    ]
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def _split_module_blocks(text: str) -> tuple[str, list[str]]:
    match = _MODULE_HEADER_RE.search(text)
    if match is None:
        return text.rstrip(), []

    header = text[: match.start()].rstrip()
    modules_text = text[match.start() :]
    blocks = [
        block.strip()
        for block in re.split(
            r"(?=^\[\[modules\s*\]\])",
            modules_text,
            flags=re.MULTILINE,
        )
        if len(block.strip()) > 0
    ]
    return header, blocks


def _render_groups(
    header: str,
    groups: tuple[tuple[str | None, tuple[str, ...]], ...],
) -> str:
    rendered_groups: list[str] = []
    for section_header, group in groups:
        if len(group) == 0:
            continue
        rendered_group = "\n\n".join(group)
        if section_header is not None:
            rendered_group = f"{section_header}\n\n{rendered_group}"
        rendered_groups.append(rendered_group)

    rendered_modules = "\n\n\n".join(rendered_groups)
    if len(header) == 0:
        return rendered_modules + "\n"
    if len(rendered_modules) == 0:
        return header + "\n"
    return header + "\n\n" + rendered_modules + "\n"


def normalize_tach_text(
    text: str,
    *,
    tach: TachConfig,
    config: PolicyConfig,
) -> str:
    clean_text = _strip_generated_section_headers(text)
    parse_tach_config(clean_text)
    header, blocks = _split_module_blocks(clean_text)
    if len(blocks) == 0:
        raise RuntimeError("No [[modules]] sections found")

    blocks = [
        normalize_depends_on(block, module_specs=config.modules) for block in blocks
    ]
    normalized_tach = parse_tach_config(
        _render_groups(header, ((None, tuple(blocks)),))
    )
    if normalized_tach.module_paths != tach.module_paths:
        raise RuntimeError("Tach normalization changed the exact module set")

    zero_dependency_production, production, dev_only = _tach_groups(
        blocks,
        config=config,
    )
    return _render_groups(
        header,
        (
            (_TACH_ZERO_DEPENDENCY_PRODUCTION_HEADER, zero_dependency_production),
            (_TACH_PRODUCTION_HEADER, production),
            (_TACH_DEV_ONLY_HEADER, dev_only),
        ),
    )


def _sort_list_fields(text: str) -> str:
    updated = text
    for field_name in _LIST_FIELD_NAMES:
        pattern = re.compile(
            rf"(?ms)^(?P<prefix>{re.escape(field_name)}\s*=\s*)"
            r"\[(?P<body>.*?)\]"
        )

        def replace(
            match: re.Match[str],
            field_name: str = field_name,
        ) -> str:
            if "#" in match.group("body"):
                return match.group(0)
            parsed = tomllib.loads(f"{field_name} = [{match.group('body')}]")
            values = cast(list[str], parsed[field_name])
            formatted = ", ".join(json.dumps(value) for value in sorted(values))
            return f"{match.group('prefix')}[{formatted}]"

        updated = pattern.sub(replace, updated)
    return updated


def normalize_policy_text(text: str) -> str:
    clean_text = _strip_generated_section_headers(text)
    config = parse_policy_config(clean_text)
    updated = _sort_list_fields(clean_text)
    header, blocks = _split_module_blocks(updated)

    production: list[str] = []
    dev_only: list[str] = []
    for block in blocks:
        path, _ = _block_identity(block)
        if config.is_dev_only(path):
            dev_only.append(block)
        else:
            production.append(block)

    production.sort(key=_block_path)
    dev_only.sort(key=_block_path)
    return _render_groups(
        header,
        (
            (_POLICY_PRODUCTION_HEADER, tuple(production)),
            (_POLICY_DEV_ONLY_HEADER, tuple(dev_only)),
        ),
    )
