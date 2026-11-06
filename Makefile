.DEFAULT_GOAL := ci

.PHONY: ci precommit ruff standards-check

standards-check:
	uv run --locked nox-py-standards check

ruff: standards-check
	uv run --locked ruff format .
	uv run --locked ruff check --fix .
	uv run --locked ruff format .

precommit:
	uv run --locked pre-commit run --all-files --show-diff-on-failure

ci: standards-check
	uv run --locked ruff format --check .
	uv run --locked ruff check .
	uv run --locked pyright
