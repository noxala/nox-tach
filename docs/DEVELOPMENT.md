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
`make ci` and the clean private Git install. Add any future CI jobs to its `needs`
list; keep this name stable.

[Package tests](../dev/tests/test_package.py) build a wheel and sdist, rebuild the
wheel from the sdist, and install both wheels non-editably in clean environments.
They run both CLI entry points from unrelated consumer directories, verify
non-mutating failures and repeatable fixes, and type-check the supported API.
Do not make these pass through `PYTHONPATH`, consumer checkouts, or application
fixtures. The separate CI Git-install step proves private fetching of the tested
revision with an empty dependency cache.

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

## Private access and releases

Consumers pin a reviewed **full merged commit SHA**, including when a GitHub
release tag exists. Commit the consumer lockfile. Tags may label releases; they
do not replace the SHA in the dependency reference.

1. Review package version and API/policy compatibility. Update version expectations
   in the package metadata tests when changing the version.
2. Pass CI, merge, and record the full merged SHA. Existing tags remain fixed.
3. Verify a clean Git install of that SHA.
4. Update each consumer's development pin and lock in a separate PR and prove
   private fetching before `uv sync --locked`.

Git credentials need read access to this private repository. Configure a
developer credential mechanism or job-scoped CI helper; never embed credentials
in dependency URLs, lockfiles, or logs. A consumer's default repository-scoped
Actions token cannot fetch nox-tach. This package's own CI token can fetch itself.
If access is missing, report the prerequisite; cached installs do not prove access.

The [release-assets workflow](RELEASING.md) attaches a wheel, source distribution,
and checksums to GitHub releases after running the tagged revision's checks. It
runs on release publication or manually from `master` with an existing release tag,
including `v0.1.0`. It uses this repository's built-in token; no extra release secret
or PyPI publishing is needed. Consumer migration history is in
[EXTRACTION.md](EXTRACTION.md); it is not a prerequisite for routine development.

## Maintaining guidance

Keep [AGENTS.md](../AGENTS.md) as a short router, with detail owned by the relevant
guide. It has a 450-word budget, measured by whitespace splitting rather than a
model-specific tokenizer. Documentation checks validate local Markdown links and
heading anchors, including the router's destinations. Use inline links for these
paths and ordinary Markdown headings. Keep exact versions and graph edges in
their machine-readable authorities. Review one representative task through each
changed route to catch missing context that link checks cannot detect.
