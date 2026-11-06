# nox-tach

Development setup for the shared Tach policy engine. Implementation and package
extraction are tracked in [issue #1](https://github.com/noxala/nox-tach/issues/1).
The repository currently has no engine or installable distribution.

## Development

Install Python 3.14.10, uv 0.13.6 or newer, and Node.js 24 for Pyright, then run:

```bash
uv sync --locked
uv run pre-commit install --install-hooks --hook-type pre-commit \
  --hook-type pre-push
make ci
```

`nox-python-standards==0.2.1` is a development dependency. Complete Ruff/Pyright
settings stay visible in [pyproject.toml](pyproject.toml); the shared checker
verifies those values, exact tool pins, active versions, and manual Ruff approval.
Shared review guidance is copied into
[.noxala/PYTHON_CONVENTIONS.md](.noxala/PYTHON_CONVENTIONS.md).

`make standards-check` runs the checker. `make ruff` checks standards before native
Ruff format, lint fix, and format. `make ci` checks standards, formatting, lint, and
types without writing changes. Local hooks check standards before fixes;
pre-push also checks types. Tests will be added with the engine implementation.

## Standards updates

Update the exact published standards version and `uv.lock`, install it, then adopt
its settings explicitly:

```bash
uv run --locked nox-py-standards sync
make ci
```

Review and commit the local settings and conventions diff. Sync preserves local
paths and exceptions; tool version changes require deliberate dependency updates
and manual Ruff approval. CI and hooks never run sync automatically.
