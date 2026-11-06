# src/nox_tach/patterns.py
from __future__ import annotations


def module_within_root(module_path: str, root: str) -> bool:
    return module_path == root or module_path.startswith(f"{root}.")


def dependency_is_allowed(dependency: str, allowed_dependencies: set[str]) -> bool:
    if dependency in allowed_dependencies:
        return True

    for allowed_dependency in allowed_dependencies:
        if allowed_dependency.endswith(".**"):
            root = allowed_dependency.removesuffix(".**")
            if dependency.startswith(f"{root}."):
                return True

        if allowed_dependency.endswith(".*"):
            root = allowed_dependency.removesuffix(".*")
            prefix = f"{root}."
            if dependency.startswith(prefix):
                remainder = dependency[len(prefix) :]
                if len(remainder) > 0 and "." not in remainder and "*" not in remainder:
                    return True

    return False


def tach_pattern_parts(pattern: str) -> tuple[str, str]:
    if pattern.endswith(".**"):
        return pattern.removesuffix(".**"), "recursive"
    if pattern.endswith(".*"):
        return pattern.removesuffix(".*"), "direct"
    if "*" in pattern:
        raise RuntimeError(f"Unsupported Tach module pattern: {pattern!r}")
    return pattern, "exact"


def is_direct_module_child(module_path: str, root: str) -> bool:
    prefix = f"{root}."
    if not module_path.startswith(prefix):
        return False

    remainder = module_path[len(prefix) :]
    return len(remainder) > 0 and "." not in remainder


def tach_pattern_is_subset(candidate: str, allowed: str) -> bool:
    candidate_root, candidate_kind = tach_pattern_parts(candidate)
    allowed_root, allowed_kind = tach_pattern_parts(allowed)

    if allowed_kind == "exact":
        return candidate_kind == "exact" and candidate_root == allowed_root

    if allowed_kind == "direct":
        if candidate_kind == "exact":
            return is_direct_module_child(candidate_root, allowed_root)
        return candidate_kind == "direct" and candidate_root == allowed_root

    if candidate_kind == "exact":
        return candidate_root.startswith(f"{allowed_root}.")

    return candidate_root == allowed_root or candidate_root.startswith(
        f"{allowed_root}."
    )


def tach_pattern_is_allowed(candidate: str, allowed_patterns: set[str]) -> bool:
    return any(
        tach_pattern_is_subset(candidate, allowed_pattern)
        for allowed_pattern in allowed_patterns
    )


def module_matches_tach_patterns(
    module_path: str,
    patterns: frozenset[str],
) -> bool:
    return dependency_is_allowed(module_path, set(patterns))


def tach_patterns_overlap(left: str, right: str) -> bool:
    left_root, left_kind = tach_pattern_parts(left)
    right_root, right_kind = tach_pattern_parts(right)

    if left_kind == "exact":
        return tach_pattern_is_subset(left, right)
    if right_kind == "exact":
        return tach_pattern_is_subset(right, left)

    if left_kind == "direct" and right_kind == "direct":
        return left_root == right_root

    if left_kind == "recursive" and right_kind == "recursive":
        return (
            left_root == right_root
            or left_root.startswith(f"{right_root}.")
            or right_root.startswith(f"{left_root}.")
        )

    if left_kind == "direct":
        return left_root == right_root or left_root.startswith(f"{right_root}.")

    return right_root == left_root or right_root.startswith(f"{left_root}.")
