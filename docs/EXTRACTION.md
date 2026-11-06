# Extraction provenance and rollout

The initial engine and eight generic test modules were extracted from COMO commit
`f5b4adda58182eb142049d6797e125be606cd452` (`master`, inspected November 5, 2026),
from `tools/tach_como_extensions/` and
`test/tools_test/tach_como_extensions/`. This package starts from nox-tach commit
`2080e3442019120fdf7258d36748317016ba4fb2`, retaining its existing shared standards
setup and published `nox-python-standards==0.2.1` pin.

Implementation is tracked in [issue #1](https://github.com/noxala/nox-tach/issues/1).
The policy engine, scanner, normalizers, validators, and generic fixtures moved;
COMO's real PostgreSQL-helper policy tests, report generator, graph/policy files,
and application fixtures remain owned by COMO. Generic tests use only synthetic
consumer trees and a small local literal-message assertion helper.

| Original API | Shared API |
| --- | --- |
| `TachComoConfig` | `PolicyConfig` |
| `TachComoModuleSpec` | `ModulePolicy` |
| `TachComoTestRootSpec` | `TestRootSpec` |
| `parse_tach_como_config` | `parse_policy_config` |
| `load_tach_como_config` | `load_policy_config` |
| `normalize_tach_como_text` | `normalize_policy_text` |
| `validate_tach_como_policy_configuration` | `validate_policy_configuration` |

Imports use `nox_tach`; source headers use their new repository-relative paths.
Defaults become `tach.toml`, `nox_tach.toml`, and `pyproject.toml`. Error branding
becomes `nox-tach`; normalization diagnostics identify the selected files and give
a shell-quoted shared CLI command. The Ruff generated-comment format and Eastern
timezone rules remain unchanged. Runtime dependencies remain empty. Model fields,
TOML keys, exception categories, validation order, and normalization behavior are
preserved.

Validation of the initial extraction ran the original 95 generic cases against
the original engine and all 97 cases (95 moved plus two installed-artifact cases)
against the shared package. On the unchanged COMO configuration snapshot, parsed
model fields matched, all three normalized outputs were byte-identical under a
fixed timestamp, and ten graph-policy validators had equivalent outcomes.
Filesystem-aware validation against the complete COMO checkout and its architecture
report remains part of the consumer PR; standalone CI requires no COMO checkout.

The rollout is sequential:

1. Merge the standalone package PR after all CI checks and review.
2. Record and prove a clean private Git install of the full merged SHA.
3. Start COMO adoption from fresh `master`, including CI private-fetch credentials,
   a locked development dependency, report-generator API imports, retained real-policy
   tests, and removal of the local engine/generic tests. Compare the unchanged COMO
   snapshot before removing code, then review only extraction-related graph changes.
4. Consider Milan adoption separately.

CI verifies a clean pip Git install of each PR/push SHA, including the merged
revision on `master`. It uses a job-scoped credential helper and this repository's
read token; credentials are never embedded in package references.

A repository-scoped Actions token cannot fetch another private repository. If no
approved cross-repository credential is available, keep COMO's current engine until
that prerequisite is provisioned. Do not change visibility or bypass policy checks.
This package PR does not complete the consumer-adoption criteria in issue #1.
