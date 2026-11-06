# src/nox_tach/config.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib
from typing import cast

from nox_tach.patterns import (
    module_within_root as _is_module_within_root,
)

DEFAULT_POLICY_PATH = Path("nox_tach.toml")


@dataclass(frozen=True, slots=True, kw_only=True)
class TestRootSpec:
    path: str
    mirror_component_suffix: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ModulePolicy:
    path: str
    dependency_whitelist: frozenset[str] | None = None
    dependency_blacklist: frozenset[str] | None = None
    parents_whitelist: frozenset[str] | None = None
    external_lib_whitelist: frozenset[str] | None = None
    dev_only: bool | None = None
    test_root: bool = False
    test_infra: bool = False
    test_mirror_component_suffix: str | None = None
    collapse_references: bool = False
    collapse_references_blacklist: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True, kw_only=True)
class PolicyConfig:
    modules: tuple[ModulePolicy, ...]

    @property
    def test_roots(self) -> tuple[TestRootSpec, ...]:
        return tuple(
            TestRootSpec(
                path=spec.path,
                mirror_component_suffix=cast(str, spec.test_mirror_component_suffix),
            )
            for spec in self.modules
            if spec.test_root
        )

    def test_root_for(self, module_path: str) -> TestRootSpec | None:
        matches = tuple(
            root
            for root in self.test_roots
            if _is_module_within_root(module_path, root.path)
        )
        if len(matches) == 0:
            return None
        if len(matches) != 1:
            raise RuntimeError(
                f"Module {module_path!r} is inside multiple configured test roots"
            )
        return matches[0]

    def test_infra_root_for(self, module_path: str) -> str | None:
        matches = sorted(
            (
                spec.path
                for spec in self.modules
                if spec.test_infra and _is_module_within_root(module_path, spec.path)
            ),
            key=lambda path: len(path.split(".")),
            reverse=True,
        )
        if len(matches) == 0:
            return None
        return matches[0]

    def is_test_infra(self, module_path: str) -> bool:
        return self.test_infra_root_for(module_path) is not None

    def is_dev_only(self, module_path: str) -> bool:
        return any(
            _is_module_within_root(module_path, spec.path)
            and (spec.dev_only is True or spec.test_root or spec.test_infra)
            for spec in self.modules
        )


def _validate_module_name(module: str) -> None:
    parts = module.split(".")
    if len(parts) == 0 or any(
        len(part) == 0 or not part.isidentifier() for part in parts
    ):
        raise ValueError(f"Invalid Python module name: {module!r}")


def _validate_tach_module_pattern(module: str, *, field: str) -> None:
    root = module
    if module.endswith(".**"):
        root = module.removesuffix(".**")
    elif module.endswith(".*"):
        root = module.removesuffix(".*")
    elif "*" in module:
        raise ValueError(
            f"{field} supports only exact Tach modules, '.*', or '.**' patterns, "
            f"got {module!r}"
        )

    if len(root) == 0 or "*" in root:
        raise ValueError(
            f"{field} supports only exact Tach modules, '.*', or '.**' patterns, "
            f"got {module!r}"
        )
    _validate_module_name(root)


def _string_list(
    value: object,
    *,
    field: str,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a TOML array of strings")

    result: list[str] = []
    for item in cast(list[object], value):
        if not isinstance(item, str):
            raise ValueError(f"{field} must be a TOML array of strings")
        item = item.strip()
        if len(item) == 0:
            raise ValueError(f"{field} must not contain blank entries")
        result.append(item)

    if len(result) != len(set(result)):
        raise ValueError(f"{field} must not contain duplicate entries")
    return tuple(result)


def _optional_string_list(
    spec: dict[str, object],
    *,
    key: str,
    field: str,
) -> tuple[str, ...] | None:
    if key not in spec:
        return None
    return _string_list(spec[key], field=f"{field}.{key}")


def _true_marker(
    spec: dict[str, object],
    *,
    key: str,
    field: str,
) -> bool:
    if key not in spec:
        return False

    value = spec[key]
    if not isinstance(value, bool):
        raise ValueError(f"{field}.{key} must be a boolean")
    if not value:
        raise ValueError(
            f"{field}.{key} is a role marker and may only be true; omit it otherwise"
        )
    return True


def _validate_test_role_configuration(
    specs: tuple[ModulePolicy, ...],
) -> None:
    test_roots = tuple(spec for spec in specs if spec.test_root)

    for child in test_roots:
        ancestors = sorted(
            (
                ancestor.path
                for ancestor in test_roots
                if ancestor.path != child.path
                and child.path.startswith(f"{ancestor.path}.")
            ),
            key=lambda path: len(path.split(".")),
            reverse=True,
        )
        if len(ancestors) == 0:
            continue

        raise ValueError(
            f"Module {child.path!r} sets test_root = true below test root "
            f"{ancestors[0]!r}. Test roots must be disjoint."
        )

    for infra in (spec for spec in specs if spec.test_infra):
        missing_surfaces: list[str] = []
        if infra.dependency_whitelist is None:
            missing_surfaces.append("dependency_whitelist")
        if infra.external_lib_whitelist is None:
            missing_surfaces.append("external_lib_whitelist")
        if len(missing_surfaces) > 0:
            raise ValueError(
                f"Module {infra.path!r} sets test_infra = true but does not "
                "explicitly declare: " + ", ".join(missing_surfaces)
            )

        owning_roots = tuple(
            root.path for root in test_roots if infra.path.startswith(f"{root.path}.")
        )
        if len(owning_roots) == 1:
            continue

        if len(owning_roots) == 0:
            raise ValueError(
                f"Module {infra.path!r} sets test_infra = true but is not a strict "
                "descendant of a configured test root"
            )
        raise ValueError(
            f"Module {infra.path!r} belongs to multiple configured test roots: "
            + ", ".join(repr(path) for path in sorted(owning_roots))
        )


def _validate_dev_only_monotonicity(
    specs: tuple[ModulePolicy, ...],
) -> None:
    dev_only_roots = tuple(
        spec
        for spec in specs
        if spec.dev_only is True or spec.test_root or spec.test_infra
    )

    for child in specs:
        if child.dev_only is not False:
            continue

        inherited_from = sorted(
            (
                ancestor.path
                for ancestor in dev_only_roots
                if _is_module_within_root(child.path, ancestor.path)
            ),
            key=lambda path: len(path.split(".")),
            reverse=True,
        )
        if len(inherited_from) == 0:
            continue

        ancestor_path = inherited_from[0]
        raise ValueError(
            f"Module {child.path!r} explicitly sets dev_only = false, but "
            f"{ancestor_path!r} establishes effective dev-only status. Descendants "
            "of a dev-only, test-root, or test-infrastructure module may not disable "
            "dev-only status."
        )


def _parse_modules(value: object) -> tuple[ModulePolicy, ...]:
    if not isinstance(value, list):
        raise ValueError("modules must be an array of TOML tables")

    specs: list[ModulePolicy] = []
    seen_paths: set[str] = set()
    allowed_fields = {
        "path",
        "dependency_whitelist",
        "dependency_blacklist",
        "parents_whitelist",
        "external_lib_whitelist",
        "dev_only",
        "test_root",
        "test_infra",
        "test_mirror_component_suffix",
        "collapse_references",
        "collapse_references_blacklist",
    }

    for index, raw_spec in enumerate(cast(list[object], value)):
        field = f"modules[{index}]"
        if not isinstance(raw_spec, dict):
            raise ValueError(f"{field} must be a TOML table")
        spec = cast(dict[str, object], raw_spec)

        unknown_fields = sorted(set(spec) - allowed_fields)
        if len(unknown_fields) > 0:
            formatted = ", ".join(repr(name) for name in unknown_fields)
            raise ValueError(f"{field} has unknown field(s): {formatted}")

        path_obj = spec.get("path")
        if not isinstance(path_obj, str) or len(path_obj.strip()) == 0:
            raise ValueError(f"{field}.path must be a non-blank string")

        path = path_obj.strip()
        _validate_module_name(path)

        if path in seen_paths:
            raise ValueError(f"modules contains duplicate policy for path {path!r}")
        seen_paths.add(path)

        dependency_whitelist = _optional_string_list(
            spec,
            key="dependency_whitelist",
            field=field,
        )
        dependency_blacklist = _optional_string_list(
            spec,
            key="dependency_blacklist",
            field=field,
        )
        if dependency_whitelist is not None and dependency_blacklist is not None:
            raise ValueError(
                f"{field} may not specify both dependency_whitelist and "
                "dependency_blacklist"
            )

        parents_whitelist = _optional_string_list(
            spec,
            key="parents_whitelist",
            field=field,
        )
        external_lib_whitelist = _optional_string_list(
            spec,
            key="external_lib_whitelist",
            field=field,
        )

        dev_only: bool | None = None
        if "dev_only" in spec:
            dev_only_obj = spec["dev_only"]
            if not isinstance(dev_only_obj, bool):
                raise ValueError(f"{field}.dev_only must be a boolean")
            dev_only = dev_only_obj

        test_root = _true_marker(spec, key="test_root", field=field)
        test_infra = _true_marker(spec, key="test_infra", field=field)
        if test_root and test_infra:
            raise ValueError(
                f"{field} may not specify both test_root = true and test_infra = true"
            )

        test_mirror_component_suffix: str | None = None
        if "test_mirror_component_suffix" in spec:
            suffix_obj = spec["test_mirror_component_suffix"]
            if not isinstance(suffix_obj, str):
                raise ValueError(
                    f"{field}.test_mirror_component_suffix must be a string"
                )
            test_mirror_component_suffix = suffix_obj
            if not test_root:
                raise ValueError(
                    f"{field}.test_mirror_component_suffix requires test_root = true"
                )
        elif test_root:
            raise ValueError(
                f"{field}.test_root = true requires test_mirror_component_suffix"
            )

        collapse_references_obj = spec.get("collapse_references", False)
        if not isinstance(collapse_references_obj, bool):
            raise ValueError(f"{field}.collapse_references must be a boolean")
        collapse_references = collapse_references_obj

        collapse_references_blacklist = _optional_string_list(
            spec,
            key="collapse_references_blacklist",
            field=field,
        )
        if collapse_references_blacklist is None:
            collapse_references_blacklist = ()
        elif not collapse_references:
            raise ValueError(
                f"{field}.collapse_references_blacklist requires "
                "collapse_references = true"
            )

        for list_field, values in (
            ("dependency_whitelist", dependency_whitelist),
            ("dependency_blacklist", dependency_blacklist),
            ("parents_whitelist", parents_whitelist),
        ):
            if values is None:
                continue
            for module_pattern in values:
                _validate_tach_module_pattern(
                    module_pattern,
                    field=f"{field}.{list_field}",
                )

        if external_lib_whitelist is not None:
            for external_lib in external_lib_whitelist:
                _validate_module_name(external_lib)

        for consumer in collapse_references_blacklist:
            _validate_tach_module_pattern(
                consumer,
                field=f"{field}.collapse_references_blacklist",
            )

        specs.append(
            ModulePolicy(
                path=path,
                dependency_whitelist=(
                    None
                    if dependency_whitelist is None
                    else frozenset(dependency_whitelist)
                ),
                dependency_blacklist=(
                    None
                    if dependency_blacklist is None
                    else frozenset(dependency_blacklist)
                ),
                parents_whitelist=(
                    None if parents_whitelist is None else frozenset(parents_whitelist)
                ),
                external_lib_whitelist=(
                    None
                    if external_lib_whitelist is None
                    else frozenset(external_lib_whitelist)
                ),
                dev_only=dev_only,
                test_root=test_root,
                test_infra=test_infra,
                test_mirror_component_suffix=test_mirror_component_suffix,
                collapse_references=collapse_references,
                collapse_references_blacklist=frozenset(collapse_references_blacklist),
            )
        )

    result = tuple(specs)
    _validate_test_role_configuration(result)
    _validate_dev_only_monotonicity(result)
    return result


def parse_policy_config(text: str) -> PolicyConfig:
    parsed: dict[str, object] = tomllib.loads(text)
    allowed_fields = {"modules"}
    unknown_fields = sorted(set(parsed) - allowed_fields)
    if len(unknown_fields) > 0:
        formatted = ", ".join(repr(name) for name in unknown_fields)
        raise ValueError(f"nox_tach.toml has unknown top-level field(s): {formatted}")

    return PolicyConfig(
        modules=_parse_modules(parsed.get("modules", [])),
    )


def load_policy_config(
    path: Path = DEFAULT_POLICY_PATH,
) -> PolicyConfig:
    return parse_policy_config(path.read_text(encoding="utf-8"))
