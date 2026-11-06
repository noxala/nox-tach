# Markdown module maps

The installed package renders a readable projection of a repository's declared
Tach graph, effective test/dev roles, dependency policies, and entry points.
It uses only configuration and stdlib; it does not import the consumer, invoke
Tach, inspect a database, or depend on a documentation framework.

## Configuration

Add a short, single-line description to each top-level module's policy block in
`nox_tach.toml`. A description-only block adds no dependency restrictions:

```toml
[[modules]]
path = "example"
description = "Application use cases and domain behavior."
```

`description` is optional for ordinary policy checks. Map generation requires
descriptions for every exact top-level Tach module and rejects stale policy paths.
Normalizing policy preserves this metadata. Nested modules may also carry a
description; the package summary uses descriptions at top-level paths.

The title comes from `[project].name` in `pyproject.toml`. Entry points come from
`[project.scripts]` and the optional `[tool.fastapi].entrypoint`; installing
FastAPI is unnecessary.

## Commands

```bash
uv run nox-tach docs
uv run nox-tach docs --check
```

Both `nox-tach` and `python -m nox_tach` support these commands. The default output
is `docs/generated/MODULE_MAP.md`. `--output` accepts an absolute path or a path
relative to the selected Tach file's parent. Config options retain their existing
meaning; relative input paths resolve from the working directory:

```bash
nox-tach docs --tach-path /project/graph.toml \
    --policy-path /project/rules.toml --pyproject-path /project/project.toml \
    --output reference/modules.md
```

Generation creates only the output file and its missing parent directories.
`--check` compares deterministic output, prints a diff and regeneration command
on drift, and writes nothing, including when the output is missing. Output may
not replace an input file. Neither command normalizes or rewrites configuration.

The map preserves explicit dependency patterns and distinguishes declared policy
from effective dev-only status. It is a report, not a substitute for native Tach
or nox-tach policy checks.

To adopt it, move package descriptions into policy, replace the local generator
with `nox-tach docs`, and run `nox-tach docs --check` in CI. This repository uses
that same workflow through `make docs` and `make docs-check`.
