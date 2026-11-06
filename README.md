# nox-tach

Architectural policy and configuration normalization for Python projects using
[upstream Tach](https://github.com/gauge-sh/tach). Tach checks actual imports;
nox-tach adds inherited restrictions, test dependency rules, and deterministic
configuration maintenance. It also generates readable Markdown module maps.
The installed engine uses only Python's standard library.

## Install

Install the wheel from a [published release](https://github.com/noxala/nox-tach/releases),
for example v0.3.0:

```bash
python -m pip install 'nox-tach @ https://github.com/noxala/nox-tach/releases/download/v0.3.0/nox_tach-0.3.0-py3-none-any.whl'
```

Public downloads require no cross-repository credentials. Record the release URL
in your development dependencies and commit the lockfile; see
[consumer updates and releases](docs/DEVELOPMENT.md#consumer-updates-and-releases)
for the update procedure and exact-commit installs of unreleased revisions.
Install upstream Tach separately as a development tool.
[Package metadata](pyproject.toml) defines the supported Python range.
Linux and macOS require `America/New_York` timezone data for generated Ruff comments.

## Minimal consumer

For a package at `src/example/__init__.py`, create these three files.

`tach.toml`:

```toml
source_roots = ["src"]
exact = true
root_module = "forbid"

[[modules]]
path = "example"
depends_on = []
```

`nox_tach.toml`:

```toml
[[modules]]
path = "example"
dependency_whitelist = []
external_lib_whitelist = []
```

Add this managed field to `pyproject.toml`:

```toml
[tool.ruff.lint.isort]
known-first-party = []
```

Then run:

```bash
uv run tach sync
uv run nox-tach --fix
uv run tach check
uv run nox-tach --check
```

This policy permits the example package's own subtree and stdlib.
See [policy semantics](docs/POLICY.md) for other restrictions.

Exactly one of `--check` and `--fix` is required. Defaults are the three filenames
above in the current directory. Override them with `--tach-path`, `--policy-path`,
and `--pyproject-path`. `python -m nox_tach` is the equivalent module entry point.
Relative source roots resolve from the selected Tach file's parent.

`--check` never writes. `--fix` validates topology, normalizes, then checks policy;
a later policy failure can leave normalized files to review. It never creates
module boundaries. Declare `source_roots` explicitly, including `["."]` for a
repository-root layout.

For package changes, start with [AGENTS.md](AGENTS.md).
The [architecture guide](docs/ARCHITECTURE.md) maps implementation/tests and the
supported typed API; [development](docs/DEVELOPMENT.md) covers verification.

## Module maps

Add a `description` to each top-level module's policy block, then run
`uv run nox-tach docs`. Use `uv run nox-tach docs --check` in CI to detect drift.
The [module-map guide](docs/MODULE_MAP.md) describes inputs, output paths, and
adopting the shared generator. See this repository's
[generated map](docs/generated/MODULE_MAP.md).
