# nox-tach

This repository currently contains development tooling only. The policy engine
extraction is tracked in [issue #1](https://github.com/noxala/nox-tach/issues/1).

Read [.noxala/PYTHON_CONVENTIONS.md](.noxala/PYTHON_CONVENTIONS.md) before Python
changes. `pyproject.toml` and `uv.lock` own Python, dependencies, and complete local
Ruff/Pyright settings.

Run `make standards-check` before generators or fixes. Explicit
`uv run --locked nox-py-standards sync` adopts shared settings and conventions;
review and commit the diff. Keep manual Ruff approval and tool pins aligned.

For Python edits, run `make ruff` until a full pass makes no further changes. Run
`make ci` before opening a PR. CI checks standards before formatting, lint, and
typing, and never syncs settings or fixes source.

Keep the future policy engine independent of consumer repositories. Configure
package builds and source discovery when the implementation is introduced.
