# Extraction provenance and rollout

This is historical migration evidence, not the routine contributor entry point.
Use [AGENTS.md](../AGENTS.md) for task routing and
[DEVELOPMENT.md](DEVELOPMENT.md) for current verification and release procedures.

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
timezone rules remain unchanged. Runtime dependencies remain empty. The initial
extraction preserved model fields, TOML keys, exception categories, validation order,
and normalization behavior. Version 0.2.0 makes `collapse_references_except` the
sole accepted key for consumers whose references must remain explicit, replacing
`collapse_references_blacklist`. See the [migration example](POLICY.md#normalization-and-ruff).

The subsequent guidance review deliberately requires explicit `source_roots`.
Unlike the extraction baseline's implicit `["."]`, current consumers must declare
`source_roots = ["."]` or their actual source directories. See
[current policy](POLICY.md#configuration-and-source-roots).

Validation of the initial extraction ran the original 95 generic cases against
the original engine and all 97 cases (95 moved plus two installed-artifact cases)
against the shared package. On the unchanged COMO configuration snapshot, parsed
model fields matched, all three normalized outputs were byte-identical under a
fixed timestamp, and ten graph-policy validators had equivalent outcomes.
Filesystem-aware validation against the complete COMO checkout and its architecture
report belongs to the consumer adoption; standalone CI requires no COMO checkout.

## Completed rollout

The extraction and COMO adoption are complete. Merged
[COMO #523](https://github.com/noxala/como/pull/523) consumes the public
[nox-tach v0.2.0 wheel](https://github.com/noxala/nox-tach/releases/tag/v0.2.0),
with its URL and SHA256 recorded in `uv.lock`. The post-merge
[consumer CI](https://github.com/noxala/como/actions/runs/42251636985) passed.
COMO owns its report-generator integration and real-policy tests; its local
engine and moved generic tests have been replaced by the shared package. Its
collapse exception keys use `collapse_references_except`.

The original private-fetch prerequisite is obsolete: the repository and released
assets are public, so consumers need no cross-repository download credentials.
Use [consumer updates](DEVELOPMENT.md#consumer-updates-and-releases) for the current
release-wheel and lockfile procedure. Milan adoption remains a separate decision.

CI verifies a clean pip Git install of each tested PR/push commit without a
credential helper and checks both CLI entry points outside the checkout. This
retains exact-revision validation alongside the installed-artifact tests.
