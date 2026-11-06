# Development

## Setup

Use the Python version required by [pyproject.toml](../pyproject.toml) and the
Node/uv versions selected by [CI](../.github/workflows/ci.yml). The
[lockfile](../uv.lock) records resolved dependencies. System timezone data must
include `America/New_York`.

```bash
uv sync --locked
uv run --locked pre-commit install --install-hooks --hook-type pre-commit --hook-type pre-push
make standards-check
```

Make targets invoke the project tools through `uv run --locked`; they do not require
activating the environment. Tests live under `dev/tests`; `src` and `dev` are
separate source roots for native Tach.

## Verification

| Task | Command |
| --- | --- |
| Focused iteration | `uv run --locked pytest dev/tests/nox_tach_test/runner_test.py` (choose tests from the [ownership map](ARCHITECTURE.md#ownership-map)) |
| Agent guidance and documentation | `make docs-check` |
| Python formatting/fixes | `make ruff`, repeated until a full pass makes no edits |
| Complete PR verification | `make ci` |
| Explicit wheel/sdist build | `make build` |

[Makefile](../Makefile) owns command ordering. CI checks standards first, then
guidance, formatting, lint, typing, policy, and the complete test suite.
Tach impact-based test selection is disabled in project pytest settings.

CI and release jobs use GitHub-hosted Ubuntu runners. Public pull requests execute
in GitHub-managed virtual machines.

In repository branch protection or rulesets, require the **`ci-gate`** check.
The final job in [CI](../.github/workflows/ci.yml) runs even if its dependencies
fail or are skipped, and passes only when every dependency succeeds. It covers
`make ci` and the clean Git install. Add any future CI jobs to its `needs`
list; keep this name stable.

[Package tests](../dev/tests/test_package.py) build a wheel and sdist, rebuild the
wheel from the sdist, and install both wheels non-editably in clean environments.
They run both CLI entry points from unrelated consumer directories, verify
non-mutating failures and repeatable fixes, and type-check the supported API.
Do not make these pass through `PYTHONPATH`, consumer checkouts, or application
fixtures. The separate CI Git-install step installs the exact tested commit from
the public repository with an empty dependency cache and runs both CLI entry points
outside the checkout.

Before changing this repository's module declarations or generated configuration,
run `make standards-check`, then native `uv run --locked tach sync`,
`uv run --locked nox-tach --fix`, and `make policy-check`. Review the resulting
diff; policy violations require an architectural decision, not automatic widening.

## Shared standards

[Python conventions](../.noxala/PYTHON_CONVENTIONS.md) and complete Ruff/Pyright
settings are checked against the installed standards release.
To adopt an update, explicitly update the development dependency and lock, install
it, then run `uv run --locked nox-py-standards sync`. Review its diff and run CI.
Ruff version approval remains manual. Checks, installation, and CI never sync
settings or approve tool upgrades.

## Consumer updates and releases

Consumers normally pin the wheel URL from a
[published GitHub release](https://github.com/noxala/nox-tach/releases).
Package downloads and public Git installs require no cross-repository credentials,
including from private consumer repositories.

1. Review the release's API/policy compatibility and select its wheel URL.
2. Update the consumer's development dependency URL and regenerate its lockfile.
   For a uv project using the `dev` group, this example updates both:

   ```bash
   uv add --group dev 'nox-tach @ https://github.com/noxala/nox-tach/releases/download/v0.2.0/nox_tach-0.2.0-py3-none-any.whl'
   uv sync --locked
   ```

3. Review and commit both `pyproject.toml` and `uv.lock`. The lockfile records the
   release URL and wheel SHA256; run the consumer's policy checks and CI in the same
   focused dependency-update PR. Installation and CI do not adopt updates implicitly.

When intentionally testing an unreleased revision, use an exact **full commit SHA**
instead of a branch or moving tag:

```bash
python -m pip install 'nox-tach @ git+https://github.com/noxala/nox-tach.git@<full-commit-sha>'
```

If a consumer adopts that revision, record the exact Git reference and update its
lockfile explicitly. A Git SHA is not required for a published release-wheel pin.
For new package releases, review compatibility, update the package version and
its metadata test expectations, pass CI, and merge before publishing a matching
release. Existing tags remain fixed.

The [release-assets workflow](RELEASING.md) attaches a wheel, source distribution,
and checksums to GitHub releases after running the tagged revision's checks. It
runs on release publication or manually from `master` with an existing release tag,
including `v0.1.0`. It uses this repository's built-in token; no extra release secret
or PyPI publishing is needed. Consumer migration history is in
[EXTRACTION.md](EXTRACTION.md); it is not a prerequisite for routine development.

## Maintaining guidance

Keep [AGENTS.md](../AGENTS.md) as a short router, with detail owned by the relevant
guide. It has a 450-word budget, measured by whitespace splitting rather than a
model-specific tokenizer. `make docs-check` runs the installed `nox-docs-check`;
document paths and the budget are declared in `[tool.nox-python-standards.docs]`
in `pyproject.toml`. The standards package owns the checker and its regression tests.
It validates local Markdown links and heading anchors, including the router's
destinations. Use inline links for these
paths and ordinary Markdown headings. Keep exact versions and graph edges in
their machine-readable authorities. Review one representative task through each
changed route to catch missing context that link checks cannot detect.
