# openflat

`openflat` is an experimental Python project for working with apartment-listing
data and, over time, building interactive decision-support dashboards.

## Repository layout

```text
openflat/
├── docs/                    # Authoritative project documentation
├── records/                 # Chronological project working record
│   ├── experiments/         # POCs, empirical checks, and dashboard prototypes
│   └── research/            # Dated notes from external research
├── src/
│   └── openflat/            # Reusable Python package
├── tests/                   # Automated package tests
├── AGENTS.md                # Repository-wide agent instructions
├── justfile                 # Reusable development commands
```

## Installation

Install [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/), then
create the environment and install all development dependencies:

```sh
just install
```

Run the complete local validation suite:

```sh
just check
```

Use `just` to see developer workflows.
