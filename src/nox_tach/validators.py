# src/nox_tach/validators.py
from __future__ import annotations

from typing import cast

from nox_tach.config import (
    ModulePolicy,
    PolicyConfig,
    TestRootSpec,
)
from nox_tach.patterns import (
    dependency_is_allowed,
    module_matches_tach_patterns,
    module_within_root,
    tach_pattern_is_allowed,
    tach_pattern_parts,
    tach_patterns_overlap,
)
from nox_tach.tach_config import TachConfig


def module_policy_chain_for_path(
    *,
    module_path: str,
    module_specs: tuple[ModulePolicy, ...],
    field: str,
) -> tuple[ModulePolicy, ...]:
    matching_specs = [
        spec
        for spec in module_specs
        if getattr(spec, field) is not None
        and module_within_root(module_path, spec.path)
    ]
    matching_specs.sort(key=lambda spec: len(spec.path.split(".")))
    return tuple(matching_specs)


def module_policy_for_path(
    *,
    module_path: str,
    module_specs: tuple[ModulePolicy, ...],
    field: str,
) -> ModulePolicy | None:
    policy_chain = module_policy_chain_for_path(
        module_path=module_path,
        module_specs=module_specs,
        field=field,
    )
    if len(policy_chain) == 0:
        return None
    return policy_chain[-1]


def validate_tach_whitelist_narrowing(
    *,
    module_specs: tuple[ModulePolicy, ...],
    field: str,
) -> None:
    violations: list[str] = []

    for child in module_specs:
        child_whitelist_obj = getattr(child, field)
        if child_whitelist_obj is None:
            continue
        child_whitelist = cast(frozenset[str], child_whitelist_obj)

        ancestor_chain = tuple(
            spec
            for spec in module_policy_chain_for_path(
                module_path=child.path,
                module_specs=module_specs,
                field=field,
            )
            if spec.path != child.path
        )
        if len(ancestor_chain) == 0:
            continue

        parent = ancestor_chain[-1]
        parent_whitelist_obj = getattr(parent, field)
        if parent_whitelist_obj is None:
            raise RuntimeError(f"Expected inherited {field} on policy {parent.path!r}")
        parent_whitelist = cast(frozenset[str], parent_whitelist_obj)
        allowed_patterns = {
            parent.path,
            f"{parent.path}.**",
            *parent_whitelist,
        }

        for candidate in sorted(child_whitelist):
            if tach_pattern_is_allowed(candidate, allowed_patterns):
                continue

            formatted_parent = ", ".join(
                repr(item) for item in sorted(parent_whitelist)
            )
            if len(formatted_parent) == 0:
                formatted_parent = "<none outside parent subtree>"

            violations.append(
                f"  {child.path!r}.{field} adds {candidate!r}, but nearest "
                f"ancestor policy {parent.path!r} permits its own subtree plus "
                f"{formatted_parent}"
            )

    if len(violations) == 0:
        return

    raise RuntimeError(
        "nox-tach whitelist narrowing policy violated. Descendant module policies "
        "may establish a narrower self-subtree and may retain only permissions "
        "available through the nearest ancestor policy; they may never widen it:\n"
        + "\n".join(violations)
    )


def validate_whitelist_policies_only_narrow(
    *,
    module_specs: tuple[ModulePolicy, ...],
) -> None:
    validate_tach_whitelist_narrowing(
        module_specs=module_specs,
        field="dependency_whitelist",
    )
    validate_tach_whitelist_narrowing(
        module_specs=module_specs,
        field="parents_whitelist",
    )


def validate_dependency_blacklists_are_canonical(
    *,
    module_specs: tuple[ModulePolicy, ...],
) -> None:
    violations: list[tuple[str, str, tuple[str, ...]]] = []

    for spec in module_specs:
        blacklist = spec.dependency_blacklist
        if blacklist is None:
            continue

        patterns_by_root: dict[str, set[str]] = {}
        for pattern in blacklist:
            root, _ = tach_pattern_parts(pattern)
            patterns_by_root.setdefault(root, set()).add(pattern)

        for root, configured_patterns in sorted(patterns_by_root.items()):
            if "." in root:
                continue

            required_patterns = {root, f"{root}.**"}
            if configured_patterns == required_patterns:
                continue

            violations.append((spec.path, root, tuple(sorted(configured_patterns))))

    if len(violations) == 0:
        return

    rendered = [
        f"  {module_path!r}.dependency_blacklist root {root!r} must be declared "
        f"exactly as [{root!r}, {f'{root}.**'!r}], but found "
        f"{list(configured_patterns)!r}"
        for module_path, root, configured_patterns in violations
    ]
    raise RuntimeError(
        "nox-tach dependency_blacklist configuration violated. Every top-level "
        "blacklist root must use the canonical exact-plus-recursive pair; exact, "
        "direct-child ('.*'), or recursive ('.**') top-level entries may not appear "
        "alone or in any other combination:\n" + "\n".join(rendered)
    )


def validate_dependency_whitelist_blacklist_conflicts(
    *,
    module_specs: tuple[ModulePolicy, ...],
) -> None:
    violations: set[tuple[str, str, str, str]] = set()

    for child in module_specs:
        child_whitelist = child.dependency_whitelist
        if child_whitelist is None:
            continue

        for ancestor in module_specs:
            if ancestor.path == child.path:
                continue
            if not module_within_root(child.path, ancestor.path):
                continue

            ancestor_blacklist = ancestor.dependency_blacklist
            if ancestor_blacklist is None:
                continue

            for whitelisted_pattern in child_whitelist:
                for blacklisted_pattern in ancestor_blacklist:
                    if not tach_patterns_overlap(
                        whitelisted_pattern,
                        blacklisted_pattern,
                    ):
                        continue
                    violations.add(
                        (
                            child.path,
                            whitelisted_pattern,
                            ancestor.path,
                            blacklisted_pattern,
                        )
                    )

    if len(violations) == 0:
        return

    rendered = [
        f"  {child_path!r}.dependency_whitelist entry "
        f"{whitelisted_pattern!r} overlaps inherited dependency_blacklist "
        f"{blacklisted_pattern!r} from ancestor policy {ancestor_path!r}"
        for (
            child_path,
            whitelisted_pattern,
            ancestor_path,
            blacklisted_pattern,
        ) in sorted(violations)
    ]
    raise RuntimeError(
        "nox-tach dependency policy configuration violated. Descendant "
        "dependency_whitelist entries may not overlap any inherited "
        "dependency_blacklist; ancestor blacklists cannot be reopened:\n"
        + "\n".join(rendered)
    )


def validate_policy_configuration(
    *,
    module_specs: tuple[ModulePolicy, ...],
) -> None:
    validate_dependency_blacklists_are_canonical(module_specs=module_specs)
    validate_whitelist_policies_only_narrow(module_specs=module_specs)
    validate_dependency_whitelist_blacklist_conflicts(module_specs=module_specs)


def validate_required_tach_settings(*, tach: TachConfig) -> None:
    violations: list[str] = []
    if tach.exact is not True:
        violations.append("  tach.toml must explicitly contain exact = true")
    if tach.root_module != "forbid":
        violations.append('  tach.toml must explicitly contain root_module = "forbid"')
    if len(violations) == 0:
        return
    raise RuntimeError(
        "nox-tach required Tach settings violated:\n" + "\n".join(violations)
    )


def validate_policy_modules_are_tach_modules(
    *,
    tach: TachConfig,
    module_specs: tuple[ModulePolicy, ...],
) -> None:
    missing_modules = sorted(
        spec.path for spec in module_specs if spec.path not in tach.module_paths
    )
    if len(missing_modules) == 0:
        return

    formatted_missing = ", ".join(repr(module) for module in missing_modules)
    raise RuntimeError(
        "Every nox_tach.toml [[modules]] path must be an exact [[modules]] path "
        f"in tach.toml. Missing modules: {formatted_missing}"
    )


_TACH_PATTERN_REFERENCE_FIELDS = (
    "dependency_whitelist",
    "dependency_blacklist",
    "parents_whitelist",
    "collapse_references_blacklist",
)


def validate_tach_pattern_references_are_tach_modules(
    *,
    tach: TachConfig,
    module_specs: tuple[ModulePolicy, ...],
) -> None:
    violations: list[tuple[str, str, str, str]] = []

    for spec in module_specs:
        for field in _TACH_PATTERN_REFERENCE_FIELDS:
            references_obj = getattr(spec, field)
            if references_obj is None:
                continue

            references = cast(frozenset[str], references_obj)
            for reference in references:
                reference_root, _ = tach_pattern_parts(reference)
                if reference_root in tach.module_paths:
                    continue
                violations.append((spec.path, field, reference, reference_root))

    if len(violations) == 0:
        return

    rendered = [
        f"  {module_path!r}.{field} entry {reference!r} is rooted at "
        f"{reference_root!r}, which is not an exact [[modules]] path in tach.toml"
        for module_path, field, reference, reference_root in sorted(violations)
    ]
    raise RuntimeError(
        "nox-tach Tach-pattern configuration violated. Every module reference in "
        "dependency_whitelist, dependency_blacklist, parents_whitelist, and "
        "collapse_references_blacklist must be rooted at an exact [[modules]] path "
        "in tach.toml:\n" + "\n".join(rendered)
    )


def validate_dev_only_dependencies(
    *,
    tach: TachConfig,
    config: PolicyConfig,
) -> None:
    violations: list[str] = []

    for module in tach.modules:
        if config.is_dev_only(module.path):
            continue

        for dependency in module.depends_on:
            dev_only_targets = sorted(
                target
                for target in tach.dependency_targets(dependency)
                if config.is_dev_only(target)
            )
            if len(dev_only_targets) == 0:
                continue

            violations.append(
                f"  non-dev module {module.path!r} depends on dev-only "
                f"{dependency!r}, which references: "
                + ", ".join(repr(path) for path in dev_only_targets)
            )

    if len(violations) == 0:
        return

    raise RuntimeError(
        "nox-tach dev-only dependency policy violated. Non-dev modules may not "
        "depend on modules inside an effectively dev-only subtree:\n"
        + "\n".join(violations)
    )


def mirrored_subject_module_path(
    test_module_path: str,
    *,
    test_root: TestRootSpec,
) -> str:
    root_parts = test_root.path.split(".")
    module_parts = test_module_path.split(".")
    if (
        len(module_parts) <= len(root_parts)
        or module_parts[: len(root_parts)] != root_parts
    ):
        raise RuntimeError(
            f"Expected a strict descendant of test root {test_root.path!r}, got "
            f"{test_module_path!r}"
        )

    subject_parts: list[str] = []
    suffix = test_root.mirror_component_suffix
    for part in module_parts[len(root_parts) :]:
        subject_part = part.removesuffix(suffix) if len(suffix) > 0 else part
        if len(subject_part) == 0:
            raise RuntimeError(
                f"Cannot derive mirrored subject from {test_module_path!r}: "
                f"component {part!r} becomes empty after removing suffix {suffix!r}"
            )
        subject_parts.append(subject_part)

    return ".".join(subject_parts)


def dependency_targets_are_test_infra(
    dependency: str,
    *,
    tach: TachConfig,
    config: PolicyConfig,
) -> bool:
    targets = tach.dependency_targets(dependency)
    return len(targets) > 0 and all(config.is_test_infra(target) for target in targets)


def validate_test_dependencies(
    *,
    tach: TachConfig,
    config: PolicyConfig,
) -> None:
    violations: set[tuple[str, str, str]] = set()

    for module in tach.modules:
        consumer_root = config.test_root_for(module.path)
        for dependency in module.depends_on:
            for target in tach.dependency_targets(dependency):
                target_root = config.test_root_for(target)
                if target_root is None:
                    continue
                if target == target_root.path:
                    violations.add((module.path, dependency, target))
                    continue
                if config.is_test_infra(target):
                    continue
                if consumer_root is not None and consumer_root.path == target_root.path:
                    continue
                violations.add((module.path, dependency, target))

    if len(violations) == 0:
        return

    rendered = [
        f"  {module_path!r} declares dependency {dependency!r}, which reaches "
        f"focused test module {target!r}"
        for module_path, dependency, target in sorted(violations)
    ]
    raise RuntimeError(
        "Tach test-dependency policy violated. Test roots are aggregate boundaries, "
        "and modules outside a test root may depend only on test infrastructure, "
        "not ordinary focused tests:\n" + "\n".join(rendered)
    )


def validate_mirrored_test_dependencies(
    *,
    tach: TachConfig,
    config: PolicyConfig,
) -> None:
    violations: list[str] = []

    for module in tach.modules:
        test_root = config.test_root_for(module.path)
        if test_root is None or module.path == test_root.path:
            continue
        if config.is_test_infra(module.path):
            continue

        subject_root = mirrored_subject_module_path(
            module.path,
            test_root=test_root,
        )
        if subject_root not in tach.module_paths:
            violations.append(
                f"  {module.path!r} mirrors {subject_root!r}, but that subject "
                "module is not an exact [[modules]] path in tach.toml"
            )
            continue

        allowed_dependencies = set(tach.subject_dependency_cone(subject_root))
        for dependency in module.depends_on:
            if dependency_targets_are_test_infra(
                dependency,
                tach=tach,
                config=config,
            ):
                continue
            if dependency_is_allowed(dependency, allowed_dependencies):
                continue
            violations.append(
                f"  {module.path!r} mirrors {subject_root!r} but depends on "
                f"{dependency!r}, which is outside that subject dependency cone"
            )

    if len(violations) == 0:
        return

    raise RuntimeError(
        "Mirrored-test Tach dependency policy violated. Every focused test module "
        "must depend only on its mirrored subject module/subtree, the transitive "
        "dependency cone authorized for that subject subtree, or declared test "
        "infrastructure:\n" + "\n".join(violations)
    )


def validate_test_infra_does_not_depend_on_focused_tests(
    *,
    tach: TachConfig,
    config: PolicyConfig,
) -> None:
    violations: set[tuple[str, str, str]] = set()

    for module in tach.modules:
        if not config.is_test_infra(module.path):
            continue

        for dependency in module.depends_on:
            for target in tach.dependency_targets(dependency):
                target_root = config.test_root_for(target)
                if target_root is None:
                    continue
                if target == target_root.path or not config.is_test_infra(target):
                    violations.add((module.path, dependency, target))

    if len(violations) == 0:
        return

    rendered = [
        f"  test infrastructure {module_path!r} declares dependency "
        f"{dependency!r}, which reaches focused test boundary {target!r}"
        for module_path, dependency, target in sorted(violations)
    ]
    raise RuntimeError(
        "Tach test-infrastructure dependency policy violated. Reusable test "
        "infrastructure may depend on production/dev modules and other declared "
        "test infrastructure according to ordinary policy, but may not depend on "
        "ordinary focused tests or a test-root aggregate:\n" + "\n".join(rendered)
    )


def validate_unique_mirrored_subjects(
    *,
    tach: TachConfig,
    config: PolicyConfig,
) -> None:
    modules_by_subject: dict[tuple[str, str], list[str]] = {}

    for module in tach.modules:
        test_root = config.test_root_for(module.path)
        if test_root is None or module.path == test_root.path:
            continue
        if config.is_test_infra(module.path):
            continue

        subject = mirrored_subject_module_path(module.path, test_root=test_root)
        modules_by_subject.setdefault((test_root.path, subject), []).append(module.path)

    collisions = {
        key: tuple(sorted(module_paths))
        for key, module_paths in modules_by_subject.items()
        if len(module_paths) > 1
    }
    if len(collisions) == 0:
        return

    rendered = [
        f"  test root {test_root!r} maps multiple exact test modules to subject "
        f"{subject!r}: {', '.join(repr(path) for path in module_paths)}"
        for (test_root, subject), module_paths in sorted(collisions.items())
    ]
    raise RuntimeError(
        "Tach mirrored-test identity policy violated. Within one test root, each "
        "mirrored subject must have exactly one exact test-module identity:\n"
        + "\n".join(rendered)
    )


def validate_dependency_whitelists(
    *,
    tach: TachConfig,
    module_specs: tuple[ModulePolicy, ...],
) -> None:
    violations: list[str] = []

    for module in tach.modules:
        policy = module_policy_for_path(
            module_path=module.path,
            module_specs=module_specs,
            field="dependency_whitelist",
        )
        if policy is None:
            continue

        configured_whitelist = policy.dependency_whitelist
        if configured_whitelist is None:
            raise RuntimeError(
                f"Expected dependency_whitelist on policy {policy.path!r}"
            )

        allowed_dependencies = {
            policy.path,
            f"{policy.path}.**",
            *configured_whitelist,
        }
        for dependency in module.depends_on:
            if dependency_is_allowed(dependency, allowed_dependencies):
                continue

            formatted_allowed = ", ".join(
                repr(allowed_dependency)
                for allowed_dependency in sorted(configured_whitelist)
            )
            if len(formatted_allowed) == 0:
                formatted_allowed = "<none outside its own subtree>"

            violations.append(
                f"  {module.path!r} depends on {dependency!r}, but policy root "
                f"{policy.path!r} has dependency_whitelist {formatted_allowed}"
            )

    if len(violations) == 0:
        return

    raise RuntimeError(
        "Tach dependency_whitelist policy violated. A configured module and its "
        "descendants may depend on that policy's own subtree plus only the exact "
        "Tach dependency patterns listed in dependency_whitelist:\n"
        + "\n".join(violations)
    )


def validate_dependency_blacklists(
    *,
    tach: TachConfig,
    module_specs: tuple[ModulePolicy, ...],
) -> None:
    violations: list[tuple[str, str, tuple[str, ...]]] = []

    for module in tach.modules:
        policy_chain = module_policy_chain_for_path(
            module_path=module.path,
            module_specs=module_specs,
            field="dependency_blacklist",
        )
        if len(policy_chain) == 0:
            continue

        blacklisted_patterns: set[str] = set()
        for policy in policy_chain:
            configured_blacklist = policy.dependency_blacklist
            if configured_blacklist is None:
                raise RuntimeError(
                    f"Expected dependency_blacklist on policy {policy.path!r}"
                )
            blacklisted_patterns.update(configured_blacklist)

        for target, dependency_path in tach.transitive_dependency_paths(
            module.path
        ).items():
            if not module_matches_tach_patterns(
                target,
                frozenset(blacklisted_patterns),
            ):
                continue
            violations.append((module.path, target, dependency_path))

    if len(violations) == 0:
        return

    rendered = [
        f"  {module_path!r} reaches blacklisted module {target!r}: "
        + " -> ".join(dependency_path)
        for module_path, target, dependency_path in sorted(violations)
    ]
    raise RuntimeError(
        "Tach dependency_blacklist policy violated. A configured module and its "
        "descendants may not directly or transitively depend on any Tach module "
        "matching an inherited dependency_blacklist pattern; blacklisted modules "
        "must not appear anywhere in their dependency cone:\n" + "\n".join(rendered)
    )


def validate_parents_whitelists(
    *,
    tach: TachConfig,
    module_specs: tuple[ModulePolicy, ...],
) -> None:
    violations: set[tuple[str, str, str, str]] = set()

    for parent_module in tach.modules:
        for dependency in parent_module.depends_on:
            for target_path in tach.dependency_targets(dependency):
                policy = module_policy_for_path(
                    module_path=target_path,
                    module_specs=module_specs,
                    field="parents_whitelist",
                )
                if policy is None:
                    continue

                parents_whitelist = policy.parents_whitelist
                if parents_whitelist is None:
                    raise RuntimeError(
                        f"Expected parents_whitelist on policy {policy.path!r}"
                    )

                if module_within_root(parent_module.path, policy.path):
                    continue
                if dependency_is_allowed(
                    parent_module.path,
                    set(parents_whitelist),
                ):
                    continue

                violations.add(
                    (parent_module.path, dependency, target_path, policy.path)
                )

    if len(violations) == 0:
        return

    rendered: list[str] = []
    for parent_path, dependency, target_path, policy_path in sorted(violations):
        policy = module_policy_for_path(
            module_path=target_path,
            module_specs=module_specs,
            field="parents_whitelist",
        )
        if policy is None or policy.parents_whitelist is None:
            raise RuntimeError(
                "Expected parents whitelist policy while rendering violation"
            )

        formatted_allowed = ", ".join(
            repr(parent) for parent in sorted(policy.parents_whitelist)
        )
        if len(formatted_allowed) == 0:
            formatted_allowed = "<none outside its own subtree>"

        rendered.append(
            f"  {parent_path!r} declares dependency {dependency!r}, which reaches "
            f"protected module {target_path!r}; policy root {policy_path!r} has "
            f"parents_whitelist {formatted_allowed}"
        )

    raise RuntimeError(
        "Tach parents_whitelist policy violated. A configured module and its "
        "descendants may be depended on only by that policy's own subtree plus the "
        "exact Tach module patterns listed in parents_whitelist:\n"
        + "\n".join(rendered)
    )
