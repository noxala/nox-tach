# nox-tach

This repository owns the reusable, stdlib-only Tach policy engine in `src/nox_tach`.
Read [README.md](README.md) for the CLI/API and development commands. The extraction
provenance and sequential consumer rollout are in [docs/EXTRACTION.md](docs/EXTRACTION.md).

Read [.noxala/PYTHON_CONVENTIONS.md](.noxala/PYTHON_CONVENTIONS.md) before Python
changes. `pyproject.toml` and `uv.lock` own Python, dependencies, and complete local
Ruff/Pyright settings.

Run `make standards-check` before generators or fixes. Explicit
`uv run --locked nox-py-standards sync` adopts shared settings and conventions;
review and commit the diff. Keep manual Ruff approval and tool pins aligned.

For Python edits, run `make ruff` until a full pass makes no further changes. Run
`make ci` before opening a PR. CI checks standards before formatting, lint, and
typing, and never syncs settings or fixes source.

Keep the engine independent of consumer repositories and upstream Tach at runtime.
`tach.toml` and `nox_tach.toml` enforce that boundary in CI. Generic tests live in
`tests/`; `test_package.py` builds wheel/sdist artifacts and checks clean installs,
both CLI entry points, and the typed API from unrelated directories. Keep package
discovery and `py.typed` intact when moving files. Preserve the historical Ruff
generated-comment format and timestamp behavior.
