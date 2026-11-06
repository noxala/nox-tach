# nox-tach

Reusable architectural policy checks and normalization layered on top of
[upstream Tach](https://github.com/gauge-sh/tach). The installed engine uses only
its own package and Python's standard library. Upstream Tach remains a separate
development tool in each consumer.

Supports Python `>=3.14.10,<3.15` on Linux and macOS. System timezone data must
include `America/New_York` for generated Ruff timestamps.

## Install and run

This repository is private. Install a reviewed **full merged commit SHA** using
Git credentials with read access to `noxala/nox-tach`:

```bash
python -m pip install 'nox-tach @ git+https://github.com/noxala/nox-tach.git@<full-merged-commit-sha>'
```

Consumers put that reference in their development dependencies and commit their
lockfile. Credentials belong in the developer's Git credential mechanism or a
job-scoped CI credential helper, never in dependency URLs, lockfiles, or logs.
Git and cross-repository read access must be available before `uv sync --locked`;
a consumer repository's default Actions token cannot read this private repository.
Verify an empty-cache install before adopting a new pin in CI.

```bash
# Upstream Tach discovers real import edges for already-declared boundaries.
uv run tach sync
uv run nox-tach --fix
uv run tach check
uv run nox-tach --check
# Equivalent module entry point:
uv run python -m nox_tach --check
```

Exactly one of `--check` and `--fix` is required. Defaults are `tach.toml`,
`nox_tach.toml`, and `pyproject.toml` in the current directory. Override any path:

```bash
nox-tach --check --tach-path config/tach.toml \
  --policy-path config/policy.toml --pyproject-path pyproject.toml
```

Tach source roots resolve relative to the selected Tach file's parent. Policy and
Pyproject options identify the files directly. The installed package location
never determines consumer paths. COMO retains `--policy-path tach_como.toml`.

`--check` validates without writing. `--fix` validates declared topology before
writing, normalizes the three files, then runs the same validation as `--check`.
It never creates boundaries or invokes upstream Tach. Invalid configuration and
policy violations exit nonzero; a failed post-normalization policy check can
leave normalized files to review. Repeated successful fixes are byte-identical.

## Configuration

Declare exact boundaries and real dependencies in Tach:

```toml
source_roots = ["src"]
exact = true
root_module = "forbid"

[[modules]]
path = "example"
depends_on = []
```

Declare additional policy in `nox_tach.toml`, for example a stdlib-only package:

```toml
[[modules]]
path = "example"
dependency_whitelist = []
external_lib_whitelist = []
```

Every policy and pattern root must identify an exact Tach module. The engine
supports monotone outgoing/inbound whitelists, transitive blacklists, dev-only
roles, configured test roots and infrastructure, focused test dependency cones,
and reference collapsing. See [policy semantics](docs/POLICY.md) for the keys and
inheritance rules.

Ruff integration requires `[tool.ruff.lint.isort]` and a `known-first-party` array
in `pyproject.toml`. The array is generated from Tach's top-level roots, excluding
manually maintained `known-third-party` entries. Other settings remain local.
The historical `tach_como extensions` generated comment is intentionally retained;
its Eastern-time timestamp changes only when the list/comment needs updating.

## Typed Python API

`nox_tach.config` and `nox_tach.tach_config` are the supported typed model/parser
API. Both distributions include `py.typed`.

```python
from pathlib import Path

from nox_tach.config import PolicyConfig, load_policy_config, parse_policy_config
from nox_tach.tach_config import TachConfig, parse_tach_config

policy: PolicyConfig = load_policy_config(Path("nox_tach.toml"))
assert policy == parse_policy_config(Path("nox_tach.toml").read_text())
tach: TachConfig = parse_tach_config(Path("tach.toml").read_text())
```

`PolicyConfig.modules` contains `ModulePolicy` values; `test_roots` contains
`TestRootSpec` values. `TachConfig.modules` contains `TachModuleSpec` values.
Models preserve declared fields, absent versus empty whitelists, graph queries,
effective dev status, and test-role queries. No consumer imports are required.
Other focused modules implement scanning, validation, normalization, and the CLI.

## Development and releases

Install Python 3.14.10, uv 0.13.6 or newer, and Node.js 24 for Pyright:

```bash
uv sync --locked
uv run pre-commit install --install-hooks --hook-type pre-commit \
  --hook-type pre-push
make standards-check
make ruff  # Repeat until a full pass makes no edits.
make ci
make build
```

`make ci` checks shared standards before native Ruff/Pyright, enforces the
stdlib-only engine boundary, and runs every generic and package test. Package
tests build a wheel and sdist, rebuild a wheel from that sdist, install both wheels
non-editably in clean environments, and exercise CLI/API/type checks from separate
consumer directories without `PYTHONPATH`. Test selection by Tach impact analysis
is disabled so the complete suite always runs. No database or consumer checkout
is needed.

CI also performs a fresh pip Git install of the exact PR/push revision with no
dependency cache. Its job-scoped credential helper uses this repository's token;
COMO adoption still needs its own approved cross-repository read credential.

Complete Ruff/Pyright settings and manual Ruff approval remain visible in
[pyproject.toml](pyproject.toml). To update shared standards, update the exact
`nox-python-standards` development pin and lock, install it, explicitly run
`uv run --locked nox-py-standards sync`, review the diff, and run `make ci`.
CI and hooks never sync settings or approve tool upgrades.

For a release, review the package version and API changes, pass CI, merge the
package PR, record the full merged SHA, and verify a clean Git install of that
revision. Then update each consumer's development pin and lock in its own PR,
proving private access with an empty dependency cache. Changes reach consumers
only through an explicit pin update. There is no registry publishing workflow.

[Extraction provenance and rollout](docs/EXTRACTION.md) records the initial move.
