# src/nox_tach/tach_config.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib
from typing import cast

from nox_tach.patterns import module_within_root


@dataclass(frozen=True, slots=True, kw_only=True)
class TachModuleSpec:
    path: str
    depends_on: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class TachConfig:
    source_roots: tuple[Path, ...]
    exact: bool
    root_module: str
    modules: tuple[TachModuleSpec, ...]

    @property
    def module_paths(self) -> frozenset[str]:
        return frozenset(module.path for module in self.modules)

    @property
    def modules_by_path(self) -> dict[str, TachModuleSpec]:
        return {module.path: module for module in self.modules}

    def dependency_targets(self, dependency: str) -> frozenset[str]:
        module_paths = self.module_paths
        if dependency.endswith(".**"):
            root = dependency.removesuffix(".**")
            return frozenset(
                module_path
                for module_path in module_paths
                if module_path.startswith(f"{root}.")
            )

        if dependency.endswith(".*"):
            root = dependency.removesuffix(".*")
            prefix = f"{root}."
            return frozenset(
                module_path
                for module_path in module_paths
                if module_path.startswith(prefix)
                and "." not in module_path[len(prefix) :]
            )

        if "*" in dependency:
            raise RuntimeError(f"Unsupported Tach dependency pattern {dependency!r}")

        if dependency in module_paths:
            return frozenset({dependency})
        return frozenset()

    def expanded_dependency_graph(self) -> dict[str, frozenset[str]]:
        graph: dict[str, frozenset[str]] = {}
        for module in self.modules:
            targets: set[str] = set()
            for dependency in module.depends_on:
                targets.update(self.dependency_targets(dependency))
            graph[module.path] = frozenset(targets)
        return graph

    def transitive_dependency_paths(
        self,
        module_path: str,
    ) -> dict[str, tuple[str, ...]]:
        graph = self.expanded_dependency_graph()
        visited = {module_path}
        pending: list[tuple[str, tuple[str, ...]]] = [(module_path, (module_path,))]
        result: dict[str, tuple[str, ...]] = {}
        next_index = 0

        while next_index < len(pending):
            current_module, current_path = pending[next_index]
            next_index += 1

            for dependency in sorted(graph.get(current_module, frozenset())):
                if dependency in visited:
                    continue
                visited.add(dependency)
                dependency_path = (*current_path, dependency)
                result[dependency] = dependency_path
                pending.append((dependency, dependency_path))

        return result

    def subject_dependency_cone(self, subject_root: str) -> frozenset[str]:
        roots = {
            module.path
            for module in self.modules
            if module_within_root(module.path, subject_root)
        }
        allowed_dependencies = {subject_root, f"{subject_root}.**"}
        pending = list(roots)
        visited: set[str] = set()
        modules_by_path = self.modules_by_path

        while len(pending) > 0:
            module_path = pending.pop()
            if module_path in visited:
                continue
            visited.add(module_path)

            module = modules_by_path[module_path]
            for dependency in module.depends_on:
                allowed_dependencies.add(dependency)
                pending.extend(self.dependency_targets(dependency) - visited)

        return frozenset(allowed_dependencies)


@dataclass(frozen=True, slots=True, kw_only=True)
class TachSourcePath:
    source_root: Path
    path: Path
    is_directory: bool


def _string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or len(value.strip()) == 0:
        raise ValueError(f"{field} must be a non-blank string")
    return value.strip()


def _string_list(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a TOML array of strings")

    values = tuple(_string(item, field=field) for item in cast(list[object], value))
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must not contain duplicate entries")
    return values


def parse_tach_config(text: str) -> TachConfig:
    parsed = cast(dict[str, object], tomllib.loads(text))

    if "source_roots" not in parsed:
        raise ValueError("tach.toml must explicitly declare source_roots")
    source_roots_obj = parsed["source_roots"]
    source_roots = tuple(
        Path(value)
        for value in _string_list(source_roots_obj, field="tach.toml source_roots")
    )
    if len(source_roots) == 0:
        raise ValueError("tach.toml source_roots must not be empty")

    exact = parsed.get("exact")
    if not isinstance(exact, bool):
        raise ValueError("tach.toml exact must be a boolean")

    root_module = _string(parsed.get("root_module"), field="tach.toml root_module")

    raw_modules = parsed.get("modules")
    if not isinstance(raw_modules, list):
        raise ValueError("tach.toml modules must be an array of tables")

    modules: list[TachModuleSpec] = []
    seen_paths: set[str] = set()
    for index, raw_module in enumerate(cast(list[object], raw_modules)):
        field = f"tach.toml modules[{index}]"
        if not isinstance(raw_module, dict):
            raise ValueError(f"{field} must be a TOML table")

        module = cast(dict[str, object], raw_module)
        path = _string(module.get("path"), field=f"{field}.path")
        if path in seen_paths:
            raise ValueError(f"tach.toml contains duplicate module {path!r}")
        seen_paths.add(path)

        if "depends_on" not in module:
            raise ValueError(
                f"tach.toml module {path!r} must explicitly declare depends_on"
            )

        modules.append(
            TachModuleSpec(
                path=path,
                depends_on=_string_list(
                    module["depends_on"],
                    field=f"{field}.depends_on",
                ),
            )
        )

    modules.sort(key=lambda module: module.path)
    return TachConfig(
        source_roots=source_roots,
        exact=exact,
        root_module=root_module,
        modules=tuple(modules),
    )


def source_root_path(repo_root: Path, source_root: Path) -> Path:
    if source_root.is_absolute():
        return source_root
    return repo_root / source_root


def source_path_for_module(
    *,
    repo_root: Path,
    source_roots: tuple[Path, ...],
    module_path: str,
) -> TachSourcePath:
    module_parts = module_path.split(".")
    candidates: list[TachSourcePath] = []

    for source_root in source_roots:
        root_path = source_root_path(repo_root, source_root)
        directory_path = root_path.joinpath(*module_parts)
        if directory_path.is_dir():
            candidates.append(
                TachSourcePath(
                    source_root=source_root,
                    path=directory_path,
                    is_directory=True,
                )
            )

        module_file = directory_path.with_suffix(".py")
        if module_file.is_file():
            candidates.append(
                TachSourcePath(
                    source_root=source_root,
                    path=module_file,
                    is_directory=False,
                )
            )

    if len(candidates) == 1:
        return candidates[0]

    formatted_roots = ", ".join(repr(str(root)) for root in source_roots)
    if len(candidates) == 0:
        raise ValueError(
            f"Cannot resolve Tach module {module_path!r} under source_roots "
            f"[{formatted_roots}]"
        )

    formatted_paths = ", ".join(repr(str(candidate.path)) for candidate in candidates)
    raise ValueError(
        f"Tach module {module_path!r} resolves to multiple source paths: "
        f"{formatted_paths}"
    )


def top_level_python_packages(
    *,
    repo_root: Path,
    source_roots: tuple[Path, ...],
) -> frozenset[str]:
    package_roots: dict[str, Path] = {}

    for source_root in source_roots:
        root_path = source_root_path(repo_root, source_root)
        if not root_path.is_dir():
            raise ValueError(f"Tach source root is not a directory: {root_path}")

        for path in root_path.iterdir():
            if (
                not path.is_dir()
                or not path.name.isidentifier()
                or not path.joinpath("__init__.py").is_file()
            ):
                continue

            existing = package_roots.get(path.name)
            if existing is not None and existing != path:
                raise ValueError(
                    f"Top-level Python package {path.name!r} exists in multiple "
                    f"Tach source roots: {existing} and {path}"
                )
            package_roots[path.name] = path

    return frozenset(package_roots)
