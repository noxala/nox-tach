.DEFAULT_GOAL := ci

.PHONY: ci precommit ruff standards-check test docs docs-check policy-check build

standards-check:
	uv run --locked nox-py-standards check

ruff: standards-check
	uv run --locked ruff format .
	uv run --locked ruff check --fix .
	uv run --locked ruff format .

precommit:
	uv run --locked pre-commit run --all-files --show-diff-on-failure

test:
	uv run --locked pytest

docs: standards-check
	uv run --locked nox-tach docs

docs-check:
	uv run --locked nox-docs-check
	uv run --locked nox-tach docs --check

policy-check:
	uv run --locked tach check
	uv run --locked nox-tach --check

build:
	uv build --no-sources

ci: standards-check
	$(MAKE) docs-check
	uv run --locked ruff format --check .
	uv run --locked ruff check .
	uv run --locked pyright
	$(MAKE) policy-check
	$(MAKE) test
