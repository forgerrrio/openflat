# Contributing

## Issues

The [openflat GitHub Project](https://github.com/orgs/forgerrrio/projects/1) is
the authoritative task board.

Issue types:

- `Task`: A concrete, independently completable unit of work.
- `Initiative`: A larger outcome composed of multiple tasks (as sub-issues).

Ways of working:

- Set `Area` using an appropriate value (or suggest a new one).
- Workflow: `Backlog` → `Ready` → `In progress` → `In review` → `Done`. Use `Cancelled` for abandoned work and close the issue as not planned.

## Commits

Use a type and component for every commit:

```text
<type>(<component>): <summary>
```

Types: `feat`, `fix`, `refactor`, `docs`, or `chore`.

Examples:

```text
feat(zed): add editor configuration
fix(keyd): preserve control tab navigation
docs(repo): update bootstrap guidance
```

Keep commit summary concise. You may include a more detailed body.

## Branches

Create a branch for every change and submit it through a pull request. Name it:

```text
<type>/<summary>
```

Examples: `feat/apartment-noise-data`, `chore/bump-deps`.

## Code quality

Repository uses `pre-commit` for `ruff` and `ty` checks.

## Pull requests

Every PR fires code quality checks and execution of the tests from `tests/` folder.
Before opening or updating a PR, retrieve the current repository labels from
GitHub and apply the most appropriate label for categorization.

## Releases

Releases are manually triggered against `main`, either from GitHub Actions or with
the authenticated GitHub CLI:

```console
just release patch  # or minor / major
```

The workflow uses `bump-my-version` and the latest stable Git tag to calculate the
next version. After Ruff, ty, and pytest pass, it tags the current `main` commit and
creates a GitHub Release with generated notes. Stable tags use the `X.Y.Z` format.
The workflow does not publish to PyPI (yet).
