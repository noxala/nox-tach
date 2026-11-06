# nox-tach agent guide

This repository owns the reusable, stdlib-only policy engine in
[src/nox_tach](src/nox_tach). Start with the route below, then read only the relevant
section, implementation, and tests. Search within that scope before expanding it.
Consumer repositories are unnecessary for ordinary package work.

## Task router

| Task | Read first |
| --- | --- |
| Policy parsing, inheritance, tests, or import restrictions | [Policy semantics](docs/POLICY.md), then [ownership map](docs/ARCHITECTURE.md#ownership-map) |
| Graph traversal, normalization, or CLI behavior | [Ownership and execution](docs/ARCHITECTURE.md) |
| Supported Python API or packaging | [Supported API](docs/ARCHITECTURE.md#supported-api), [package checks](docs/DEVELOPMENT.md#verification) |
| Setup, CI, standards, or releases | [Development](docs/DEVELOPMENT.md) |
| Consumer usage | [README](README.md) |
| Extraction compatibility investigation | [Historical provenance](docs/EXTRACTION.md) |

## Authorities and invariants

[pyproject.toml](pyproject.toml) owns versions, dependencies, entry points, and local
Ruff/Pyright settings; [uv.lock](uv.lock) owns resolved dependencies.
[Makefile](Makefile), [hooks](.pre-commit-config.yaml), and
[CI](.github/workflows/ci.yml) own executable workflows.
[tach.toml](tach.toml) and [nox_tach.toml](nox_tach.toml) own this repository's
enforced boundaries. The ownership map describes responsibilities, not extra
enforced edges.

Keep consumer identities in configuration and the engine independent of upstream
Tach at runtime. Preserve the supported typed API and `py.typed`.
`--check` never writes; `--fix` never invents boundaries or invokes Tach.
Require explicit source roots. Preserve deterministic normalization, manual Ruff
third-party exceptions, and the historical generated-comment/timestamp behavior.
Do not broaden policy merely to pass a check.

Before Python edits, read the checked local
[Python conventions](.noxala/PYTHON_CONVENTIONS.md).
Run `make standards-check` before generators or fixes. Standards adoption is
explicit; Ruff version approval remains manual.

## Verification and delivery

Run focused tests while iterating. For Python changes, run `make ruff` until a
complete pass makes no edits. Run `make docs-check` for guidance changes and
`make ci` before a PR; report what actually ran.
Use the [verification guide](docs/DEVELOPMENT.md#verification) for commands and
installed-artifact coverage.

Start new work from current `master`; continue an existing PR on its branch.
Request review from `denisgrenader` and enable auto-merge when supported.
Update the owning guide when behavior, boundaries, or canonical commands change.
Keep this file under 450 whitespace-delimited words; link focused detail instead
of duplicating it.
