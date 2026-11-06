# Engine architecture

Use this map to find the smallest implementation and test surface for a change.
Exact package requirements remain in [pyproject.toml](../pyproject.toml).
Policy meaning belongs in [POLICY.md](POLICY.md).

## Ownership map

Paths in the implementation column are under `src/nox_tach/`; test links are
under `tests/`. Cross-cutting tests intentionally exercise several owners.

| Responsibility | Implementation | Focused tests |
| --- | --- | --- |
| Policy models, parsing, declared/effective roles | [config.py](../src/nox_tach/config.py) | [policy config](../tests/test_policy_config.py), [test roles](../tests/test_test_role_tightening.py) |
| Exact/child/recursive patterns | [patterns.py](../src/nox_tach/patterns.py) | [policy](../tests/test_policy.py), [collapse](../tests/test_collapse_blacklist.py) |
| Tach models, source resolution, dependency traversal | [tach_config.py](../src/nox_tach/tach_config.py) | [Tach config](../tests/test_tach_config.py), [policy](../tests/test_policy.py) |
| Static external-import restrictions | [imports.py](../src/nox_tach/imports.py) | [policy](../tests/test_policy.py), [runner](../tests/test_runner.py) |
| Configuration and graph-policy enforcement | [validators.py](../src/nox_tach/validators.py) | [policy](../tests/test_policy.py), [test roles](../tests/test_test_role_tightening.py) |
| TOML grouping, sorting, reference collapsing | [normalization.py](../src/nox_tach/normalization.py) | [normalization](../tests/test_normalization_sections.py), [collapse](../tests/test_collapse_blacklist.py) |
| Ruff first-party projection | [ruff_config.py](../src/nox_tach/ruff_config.py) | [Ruff config](../tests/test_ruff_config.py) |
| File I/O, validation order, CLI | [runner.py](../src/nox_tach/runner.py), [__main__.py](../src/nox_tach/__main__.py) | [runner](../tests/test_runner.py), [installed artifacts](../tests/test_package.py) |

Keep orchestration and writes in the runner. Reuse canonical models and pattern
helpers rather than introducing a second interpretation of policy.
Consumers own their actual graph/policy files, framework fixtures, and reports.
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

[tach.toml](../tach.toml) currently declares one `nox_tach` boundary under `src`.
[nox_tach.toml](../nox_tach.toml) makes it stdlib-only. Internal module edges and
this repository's tests are not yet separate enforced boundaries.
[Issue #5](https://github.com/noxala/nox-tach/issues/5) tracks that follow-up;
the ownership map above must not be mistaken for an already enforced graph.
