set shell := ["sh", "-eu", "-c"]

default:
    @just --list

# Install the project and development dependencies.
install:
    uv sync --dev

# Format Python source and tests.
format:
    uv run ruff format .
    uv run ruff check --fix .

# Check formatting and lint rules without changing files.
lint:
    uv run ruff format --check .
    uv run ruff check .

# Type-check the reusable package and tests.
typecheck:
    uv run ty check

# Run the automated test suite.
test:
    @uv run pytest || test $? -eq 5

# Install the repository's Git pre-commit hook.
hooks:
    uv run pre-commit install

# Run every pre-commit hook against the repository.
precommit:
    uv run pre-commit run --all-files

# Trigger a GitHub release with a major, minor, or patch version bump.
release part:
    gh workflow run release.yml --ref main -f bump={{part}}

# Run all non-mutating validation tasks.
check: lint typecheck test
