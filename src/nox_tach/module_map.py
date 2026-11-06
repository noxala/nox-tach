# src/nox_tach/module_map.py
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import tomllib
from typing import cast

from nox_tach.config import (
    ModulePolicy,
    PolicyConfig,
)
from nox_tach.tach_config import (
    TachConfig,
    TachModuleSpec,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Entrypoint:
    kind: str
    name: str
    target: str


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a TOML table")
    return cast(dict[str, object], value)


def _string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or len(value.strip()) == 0:
        raise ValueError(f"{field} must be a non-blank string")
    return value.strip()


def _parse_project(text: str) -> tuple[str, tuple[Entrypoint, ...]]:
    parsed = cast(dict[str, object], tomllib.loads(text))
    entrypoints: list[Entrypoint] = []

    project_obj = parsed.get("project", {})
    project = _mapping(project_obj, field="pyproject.toml project")
    project_name = _string(project.get("name"), field="pyproject.toml project.name")
    scripts_obj = project.get("scripts", {})
    scripts = _mapping(scripts_obj, field="pyproject.toml project.scripts")
    for name, target_obj in scripts.items():
        entrypoints.append(
            Entrypoint(
                kind="CLI",
                name=name,
                target=_string(
                    target_obj,
                    field=f"pyproject.toml project.scripts.{name}",
                ),
            )
        )

    tool_obj = parsed.get("tool", {})
    tool = _mapping(tool_obj, field="pyproject.toml tool")
    fastapi_obj = tool.get("fastapi", {})
    fastapi = _mapping(fastapi_obj, field="pyproject.toml tool.fastapi")
    if "entrypoint" in fastapi:
        entrypoints.append(
            Entrypoint(
                kind="FastAPI",
                name="application",
                target=_string(
                    fastapi["entrypoint"],
                    field="pyproject.toml tool.fastapi.entrypoint",
                ),
            )
        )

    entrypoints.sort(key=lambda item: (item.kind, item.name, item.target))
    return project_name, tuple(entrypoints)


def _table_text(value: str) -> str:
    return " ".join(value.split()).replace("\\", "\\\\").replace("|", "\\|")


def _top_level(module_pattern: str) -> str:
    return module_pattern.split(".", 1)[0]


def _format_code_values(values: Sequence[str]) -> str:
    if len(values) == 0:
        return "—"
    return ", ".join(f"`{value}`" for value in values)


def _format_policy_values(values: frozenset[str]) -> str:
    return ", ".join(sorted(values))


def _policy_summary(policy: ModulePolicy | None) -> str:
    if policy is None:
        return "—"

    parts: list[str] = []
    for label, values in (
        ("dependency whitelist", policy.dependency_whitelist),
        ("dependency blacklist", policy.dependency_blacklist),
        ("parents whitelist", policy.parents_whitelist),
        ("external libraries", policy.external_lib_whitelist),
    ):
        if values is not None:
            rendered = "empty" if len(values) == 0 else _format_policy_values(values)
            parts.append(f"{label}: {rendered}")

    if policy.dev_only is True:
        parts.append("dev-only")
    elif policy.dev_only is False:
        parts.append("dev-only: false")

    if policy.test_root:
        suffix = cast(str, policy.test_mirror_component_suffix)
        parts.append(f"test root; mirror suffix: {suffix!r}")
    if policy.test_infra:
        parts.append("test infrastructure")
    if policy.collapse_references:
        parts.append("collapse references")
    if len(policy.collapse_references_except) > 0:
        parts.append(
            "collapse exclusions: "
            + _format_policy_values(policy.collapse_references_except)
        )
    if len(parts) == 0:
        return "—"
    return "; ".join(parts)


def _top_level_dependencies(
    root: str,
    modules: Sequence[TachModuleSpec],
) -> tuple[str, ...]:
    dependencies: set[str] = set()
    for module in modules:
        if module.path != root and not module.path.startswith(f"{root}."):
            continue
        for dependency in module.depends_on:
            dependency_root = _top_level(dependency)
            if dependency_root != root:
                dependencies.add(dependency_root)
    return tuple(sorted(dependencies))


def render_module_map(
    *,
    tach: TachConfig,
    config: PolicyConfig,
    pyproject_text: str,
    input_names: Sequence[str] = ("tach.toml", "nox_tach.toml", "pyproject.toml"),
) -> str:
    project_name, entrypoints = _parse_project(pyproject_text)
    policy_by_path = {policy.path: policy for policy in config.modules}
    unknown = sorted(set(policy_by_path) - tach.module_paths)
    if unknown:
        raise ValueError("Policy modules absent from tach.toml: " + ", ".join(unknown))
    top_level_modules = tuple(
        module for module in tach.modules if "." not in module.path
    )
    missing_descriptions = sorted(
        module.path
        for module in top_level_modules
        if module.path not in policy_by_path
        or policy_by_path[module.path].description is None
    )
    if len(missing_descriptions) > 0:
        raise ValueError(
            "Missing top-level module descriptions for: "
            + ", ".join(missing_descriptions)
        )

    dev_only_modules = tuple(
        module.path for module in tach.modules if config.is_dev_only(module.path)
    )

    lines: list[str] = [
        f"# Generated {_table_text(project_name)} Module Map",
        "",
        "> Generated by `nox-tach docs`. Do not edit",
        "> this file directly; update the source configuration or generator.",
        "",
        f"This map is a review aid. {_format_code_values(input_names)}",
        "remain authoritative.",
        "",
        "## Inputs and settings",
        "",
        f"- Tach exact mode: `{str(tach.exact).lower()}`",
        f"- Tach root module policy: `{tach.root_module}`",
        f"- Exact Tach modules: `{len(tach.modules)}`",
        f"- Top-level modules: `{len(top_level_modules)}`",
        f"- Effectively dev-only exact modules: `{len(dev_only_modules)}`",
        f"- Configured test roots: `{len(config.test_roots)}`",
        "",
        "## Entrypoints",
        "",
        "| Kind | Name | Target |",
        "| --- | --- | --- |",
    ]
    if len(entrypoints) == 0:
        lines.append("| — | — | — |")
    else:
        lines.extend(
            f"| {entrypoint.kind} | `{entrypoint.name}` | `{entrypoint.target}` |"
            for entrypoint in entrypoints
        )

    lines.extend(
        [
            "",
            "## Top-level package map",
            "",
            "Dependencies are aggregated from every exact Tach module in the",
            "top-level subtree. Scope reflects effective dev-only policy, including",
            "status implied by test roots and test infrastructure.",
            "",
            "| Module | Scope | Responsibility | Aggregated outgoing packages |",
            "| --- | --- | --- | --- |",
        ]
    )
    for module in top_level_modules:
        scope = "dev-only" if config.is_dev_only(module.path) else "production"
        dependencies = _top_level_dependencies(module.path, tach.modules)
        lines.append(
            f"| `{module.path}` | {scope} | "
            f"{_table_text(cast(str, policy_by_path[module.path].description))} | "
            f"{_format_code_values(dependencies)} |"
        )

    lines.extend(
        [
            "",
            "## Exact Tach modules",
            "",
            "The policy column shows policy declared at that exact path. Inherited",
            "policy still applies according to nox-tach's policy semantics.",
            "",
            "| Module | Direct `depends_on` | Effective scope | Policy declared here |",
            "| --- | --- | --- | --- |",
        ]
    )
    for module in tach.modules:
        scope = "dev-only" if config.is_dev_only(module.path) else "production"
        lines.append(
            f"| `{module.path}` | {_format_code_values(module.depends_on)} | "
            f"{scope} | {_policy_summary(policy_by_path.get(module.path))} |"
        )

    lines.extend(
        [
            "",
            "## Effective dev-only exact modules",
            "",
            _format_code_values(dev_only_modules),
            "",
        ]
    )
    return "\n".join(lines)
