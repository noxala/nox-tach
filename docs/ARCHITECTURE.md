# Engine architecture

Use this map to find the smallest implementation and test surface for a change.
Exact package requirements remain in [pyproject.toml](../pyproject.toml).
Policy meaning belongs in [POLICY.md](POLICY.md).

## Ownership map

Paths in the implementation column are under `src/nox_tach/`; test links are
under `dev/tests/`. Cross-cutting tests intentionally exercise several owners.

| Responsibility | Implementation | Focused tests |
| --- | --- | --- |
| Policy models, parsing, declared/effective roles | [config.py](../src/nox_tach/config.py) | [policy config](../dev/tests/nox_tach_test/config_test.py) |
| Exact/child/recursive patterns | [patterns.py](../src/nox_tach/patterns.py) | [policy](../dev/tests/nox_tach_test/validators_test.py), [collapse](../dev/tests/nox_tach_test/normalization_test.py) |
| Tach models, source resolution, dependency traversal | [tach_config.py](../src/nox_tach/tach_config.py) | [Tach config](../dev/tests/nox_tach_test/tach_config_test.py), [policy](../dev/tests/nox_tach_test/validators_test.py) |
| Static external-import restrictions | [imports.py](../src/nox_tach/imports.py) | [imports](../dev/tests/nox_tach_test/imports_test.py), [runner](../dev/tests/nox_tach_test/runner_test.py) |
| Configuration and graph-policy enforcement | [validators.py](../src/nox_tach/validators.py) | [policy and test roles](../dev/tests/nox_tach_test/validators_test.py) |
| TOML grouping, sorting, reference collapsing | [normalization.py](../src/nox_tach/normalization.py) | [normalization and collapse](../dev/tests/nox_tach_test/normalization_test.py) |
| Ruff first-party projection | [ruff_config.py](../src/nox_tach/ruff_config.py) | [Ruff config](../dev/tests/nox_tach_test/ruff_config_test.py) |
| Configuration-derived Markdown rendering | [module_map.py](../src/nox_tach/module_map.py) | [module map](../dev/tests/nox_tach_test/module_map_test.py), [runner](../dev/tests/nox_tach_test/runner_test.py) |
| File I/O, validation order, CLI | [runner.py](../src/nox_tach/runner.py), [__main__.py](../src/nox_tach/__main__.py) | [runner](../dev/tests/nox_tach_test/runner_test.py), [installed artifacts](../dev/tests/test_package.py) |

Keep orchestration and writes in the runner. Reuse canonical models and pattern
helpers rather than introducing a second interpretation of policy.
Consumers own their actual graph/policy files, package descriptions, and framework
fixtures. The shared renderer owns the [module-map format](MODULE_MAP.md), while
the runner owns its file I/O and CLI.
Synthetic fixtures may use illustrative consumer names without importing consumers.

## Execution contract

Upstream `tach sync` discovers actual dependencies for declared boundaries.
Upstream `tach check` checks imports against those declarations.
The nox-tach engine never invokes either command; the calling workflow owns order.

Both CLI modes parse the selected files and resolve consumer source paths relative
to the Tach file's parent, independent of the package installation directory.
The parser requires explicit, nonempty `source_roots`; `["."]` selects that parent.

- `--check`: validate declared topology, enforce dependency policy, compute canonical
  text, and reject any differences without writing.
- `--fix`: validate declared topology before writing, normalize all three files,
  then run the same check path. A post-write policy failure is not a rollback.

Preserve this order: a missing boundary must remain a conscious configuration edit.
Normalization must converge byte-for-byte, including timestamps. Keep the existing
`tach_como extensions` Ruff marker and Eastern-time timestamp until a separately
reviewed output-format change.

`docs` renders from the same canonical models. It reads all inputs before writing
only its output; `docs --check` writes nothing. Descriptions are optional policy
metadata and do not change dependency permissions. Source parsing, normalization,
and model semantics remain with their existing owners.

## Supported API

The supported typed model/parser surface is
[config.py](../src/nox_tach/config.py) and
[tach_config.py](../src/nox_tach/tach_config.py):

- `PolicyConfig`, `ModulePolicy`, `TestRootSpec`, `parse_policy_config`,
  `load_policy_config`;
- `TachConfig`, `TachModuleSpec`, `parse_tach_config`, and their graph queries.

Preserve declared fields separately from effective inherited behavior.
For example, omitted `dev_only` differs from explicit false in the model even
when both have the same effective result. Validate API changes through the
installed-package type checks, including the [py.typed marker](../src/nox_tach/py.typed).

```python
from pathlib import Path

from nox_tach.config import PolicyConfig, load_policy_config
from nox_tach.tach_config import TachConfig, parse_tach_config

policy: PolicyConfig = load_policy_config(Path("nox_tach.toml"))
tach: TachConfig = parse_tach_config(Path("tach.toml").read_text())
```

## Current repository enforcement

[tach.toml](../tach.toml) declares every production module separately, with exact
imports discovered by native Tach. [nox_tach.toml](../nox_tach.toml) limits each
module's outgoing surface, so syncing a new import cannot silently authorize it.
The package remains stdlib-only, and production cannot depend on dev-only code.

Source roots `src` and `dev` are disjoint. Tests live under `dev/tests`; the
`tests` boundary aggregates normalization integration, packaging,
guidance, and repository-policy checks. Aggregate tests need no artificial subject.

Focused boundaries under `dev/tests/nox_tach_test` use the `_test` mirror suffix:
`config_test.py` mirrors `nox_tach.config`, for example. Each may import its subject,
that subject's downstream dependency cone, and explicitly declared infrastructure.
Keep orchestration tests out of a lower-level subject's boundary.
`tests._helpers` is narrowly declared infrastructure with no first-party
permissions and only pytest as an external dependency. Exact edges and roles live
in the TOML files; update them deliberately when responsibilities change.

[Repository-policy regressions](../dev/tests/test_repository_policy.py) prove that
native Tach rejects an undeclared internal import and that policy still rejects
prohibited internal and focused-test edges after dependency synchronization.
