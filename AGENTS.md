# AGENTS.md

`openflat` explores apartment-listing data and interactive tools that support
housing decisions.

## Development environment

- `uv`-managed python 3.13
- `ruff` for linting and formatting, `ty` for typechecking, `pytest` for testing.
- see `CONTRIBUTING.md` for commit/branch/pr guidance.

## Repository map

```text
openflat/
├── docs/                    # Authoritative documentation
├── records/
│   ├── experiments/         # POCs, checks, and dashboard prototypes
│   └── research/            # Dated external research notes
├── src/openflat/            # Production-quality package code
├── tests/                   # Tests for promoted package behavior
├── justfile                 # Shared development workflows
```
