# src/nox_tach/imports.py
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
import sys

from nox_tach.config import ModulePolicy
from nox_tach.tach_config import TachConfig, source_path_for_module


@dataclass(frozen=True, slots=True, kw_only=True)
class ImportViolation:
    path: Path
    line: int
    column: int
    imported_module: str

    def render(self) -> str:
        return (
            f"{self.path}:{self.line}:{self.column}: blacklisted import "
            f"{self.imported_module!r}"
        )


def validate_python_package_name(package: str) -> None:
    parts = package.split(".")
    if len(parts) == 0 or any(
        len(part) == 0 or not part.isidentifier() for part in parts
    ):
        raise ValueError(f"Invalid Python package name: {package!r}")


def module_name_for_path(*, root: Path, package: str, path: Path) -> str:
    relative = path.relative_to(root)
    parts = list(relative.parts)
    filename = parts.pop()
    if filename == "__init__.py":
        module_parts = parts
    else:
        module_parts = [*parts, Path(filename).stem]

    if len(module_parts) == 0:
        return package
    return f"{package}.{'.'.join(module_parts)}"


def containing_package(module_name: str, path: Path) -> str:
    if path.name == "__init__.py":
        return module_name
    return module_name.rpartition(".")[0]


def resolve_import_from(
    *,
    containing_package: str,
    module: str | None,
    level: int,
) -> str:
    if level == 0:
        if module is None:
            raise ValueError("Absolute ImportFrom must specify a module")
        return module

    package_parts = containing_package.split(".")
    parent_count = level - 1
    if parent_count >= len(package_parts):
        return ""

    base_parts = package_parts[: len(package_parts) - parent_count]
    if module is not None:
        base_parts.extend(module.split("."))
    return ".".join(base_parts)


def is_allowed_import(
    module: str,
    *,
    package: str,
    whitelist: frozenset[str],
    first_party_module_paths: frozenset[str],
) -> bool:
    if module == package or module.startswith(f"{package}."):
        return True

    if any(
        module == first_party_module or module.startswith(f"{first_party_module}.")
        for first_party_module in first_party_module_paths
    ):
        return True

    if any(
        module == whitelisted_module or module.startswith(f"{whitelisted_module}.")
        for whitelisted_module in whitelist
    ):
        return True

    top_level = module.split(".", 1)[0]
    return top_level in sys.stdlib_module_names


def import_violations_for_file(
    *,
    root: Path,
    package: str,
    whitelist: frozenset[str],
    first_party_module_paths: frozenset[str],
    path: Path,
) -> list[ImportViolation]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    module_name = module_name_for_path(root=root, package=package, path=path)
    package_name = containing_package(module_name, path)
    violations: list[ImportViolation] = []

    for node in ast.walk(tree):
        imported_modules: list[str]
        import_node: ast.Import | ast.ImportFrom

        if isinstance(node, ast.Import):
            import_node = node
            imported_modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            import_node = node
            imported_modules = [
                resolve_import_from(
                    containing_package=package_name,
                    module=node.module,
                    level=node.level,
                )
            ]
        else:
            continue

        for imported_module in imported_modules:
            if len(imported_module) > 0 and is_allowed_import(
                imported_module,
                package=package,
                whitelist=whitelist,
                first_party_module_paths=first_party_module_paths,
            ):
                continue

            violations.append(
                ImportViolation(
                    path=path,
                    line=import_node.lineno,
                    column=import_node.col_offset + 1,
                    imported_module=imported_module or "<outside package>",
                )
            )

    return violations


def find_blacklisted_imports(
    root: Path,
    *,
    package: str,
    whitelist: frozenset[str] = frozenset(),
    first_party_module_paths: frozenset[str] = frozenset(),
) -> tuple[ImportViolation, ...]:
    validate_python_package_name(package)
    for whitelisted_module in whitelist:
        validate_python_package_name(whitelisted_module)

    if not root.is_dir():
        raise ValueError(f"Path must be an existing directory: {root}")

    violations: list[ImportViolation] = []
    for path in sorted(root.rglob("*.py")):
        violations.extend(
            import_violations_for_file(
                root=root,
                package=package,
                whitelist=whitelist,
                first_party_module_paths=first_party_module_paths,
                path=path,
            )
        )

    violations.sort(
        key=lambda violation: (
            str(violation.path),
            violation.line,
            violation.column,
            violation.imported_module,
        )
    )
    return tuple(violations)


def single_file_import_violations(
    *,
    path: Path,
    module_name: str,
    whitelist: frozenset[str],
    first_party_module_paths: frozenset[str],
) -> tuple[ImportViolation, ...]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    package_name = module_name.rpartition(".")[0]
    violations: list[ImportViolation] = []

    for node in ast.walk(tree):
        imported_modules: list[str]
        import_node: ast.Import | ast.ImportFrom

        if isinstance(node, ast.Import):
            import_node = node
            imported_modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            import_node = node
            imported_modules = [
                resolve_import_from(
                    containing_package=package_name,
                    module=node.module,
                    level=node.level,
                )
            ]
        else:
            continue

        for imported_module in imported_modules:
            if len(imported_module) > 0 and is_allowed_import(
                imported_module,
                package=module_name,
                whitelist=whitelist,
                first_party_module_paths=first_party_module_paths,
            ):
                continue

            violations.append(
                ImportViolation(
                    path=path,
                    line=import_node.lineno,
                    column=import_node.col_offset + 1,
                    imported_module=imported_module or "<outside package>",
                )
            )

    violations.sort(
        key=lambda violation: (
            str(violation.path),
            violation.line,
            violation.column,
            violation.imported_module,
        )
    )
    return tuple(violations)


def validate_external_lib_whitelists(
    *,
    repo_root: Path,
    tach: TachConfig,
    module_specs: tuple[ModulePolicy, ...],
) -> None:
    violations_by_module: list[
        tuple[str, frozenset[str], tuple[ImportViolation, ...]]
    ] = []

    for spec in module_specs:
        whitelist = spec.external_lib_whitelist
        if whitelist is None:
            continue

        source_path = source_path_for_module(
            repo_root=repo_root,
            source_roots=tach.source_roots,
            module_path=spec.path,
        )
        if source_path.is_directory:
            violations = find_blacklisted_imports(
                source_path.path,
                package=spec.path,
                whitelist=whitelist,
                first_party_module_paths=tach.module_paths,
            )
        else:
            violations = single_file_import_violations(
                path=source_path.path,
                module_name=spec.path,
                whitelist=whitelist,
                first_party_module_paths=tach.module_paths,
            )

        if len(violations) > 0:
            violations_by_module.append((spec.path, whitelist, violations))

    if len(violations_by_module) == 0:
        return

    rendered_modules: list[str] = []
    for module_path, whitelist, violations in violations_by_module:
        allowed_description = (
            "the Python standard library, first-party Tach modules, or "
            f"{module_path} itself"
        )
        if len(whitelist) > 0:
            formatted_whitelist = ", ".join(
                repr(module) for module in sorted(whitelist)
            )
            allowed_description += f"; external_lib_whitelist: {formatted_whitelist}"

        rendered_violations = "\n".join(
            f"    {violation.render()}" for violation in violations
        )
        rendered_modules.append(
            f"  {module_path} must import only {allowed_description}:\n"
            f"{rendered_violations}"
        )

    raise RuntimeError(
        "nox-tach external-lib whitelist policy violated:\n"
        + "\n".join(rendered_modules)
    )
