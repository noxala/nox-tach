# Policy semantics

`nox_tach.toml` accepts only `[[modules]]` at the top level. Every `path` must be
an exact Tach module. Keep consumer identities in configuration.

| Module key | Meaning |
| --- | --- |
| `dependency_whitelist` | Outgoing permissions; the declared subtree is implicit |
| `dependency_blacklist` | Prohibited outgoing targets, including transitive paths |
| `parents_whitelist` | Inbound callers; the declared subtree is implicit |
| `external_lib_whitelist` | Permitted third-party imports; stdlib and legal first-party imports remain available |
| `dev_only` | Marks the complete subtree as development infrastructure |
| `test_root` | True-only role marker declaring an aggregate test root |
| `test_mirror_component_suffix` | Required suffix rule for a test root, e.g. `_test` |
| `test_infra` | True-only role marker for reusable infrastructure below a test root |
| `collapse_references` | Collapses external references to a subtree into its root and/or recursive pattern |
| `collapse_references_blacklist` | Consumer patterns whose references remain explicit |

`collapse_references_exclude` remains accepted as the legacy spelling of
`collapse_references_blacklist`; do not set both. Collapse exceptions require
enabled collapsing. Existing TOML keys and model fields are preserved.

Patterns are exact modules, direct children (`pkg.*`), or recursive descendants
(`pkg.**`). Recursive descendants do not include the root. Each pattern root must
be an exact Tach module. For a top-level blacklist, use the canonical pair
`["pkg", "pkg.**"]`.

Omission and an empty whitelist differ. Omission adds no boundary; an empty
whitelist permits only that boundary's own subtree. Descendant outgoing and
inbound whitelists may only narrow their ancestors' permissions. A new child
whitelist replaces the implicit self-zone with the child's subtree; access to
ancestor siblings must be explicitly retained. Blacklists accumulate and cannot
be reopened by a child whitelist. A non-dev module cannot depend on an effectively
dev-only module. `dev_only = false` cannot override inherited or implied dev status.

Test roots must be disjoint and imply dev-only status. Focused boundaries below a
test root mirror subjects by removing the configured suffix from each relative
component. Every subject must be an exact Tach module; duplicate subject identities
inside one test root are rejected. Focused tests can depend on the subject subtree,
its transitive downstream dependency cone, and configured test infrastructure.
Declaring a test root does not require every physical test directory to become a
focused boundary. The aggregate root cannot be a dependency target.

Test infrastructure must be strictly below a test root and explicitly declare both
dependency and external whitelists. It does not mirror a subject and cannot depend
on ordinary focused tests or aggregate test roots. All normal policies still apply.

Tach requires explicit `source_roots`, `exact = true`, `root_module = "forbid"`,
and a `depends_on` array on every module. Every top-level Python package under a
source root needs an exact module declaration. Directory and single-file boundaries
are supported; ambiguous resolution through multiple roots is rejected.

Normalization sorts/deduplicates dependencies and groups production modules without
first-party dependencies, remaining production modules, and dev modules. Policy
blocks group production before dev, alphabetical within each group. Comments outside
managed regions and manual Ruff third-party exceptions are preserved. Source roots
remain relative to the selected Tach file, including in an installed distribution.
