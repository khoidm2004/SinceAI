# Contributing to SinceAI

## Commit convention

This project follows [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>

[optional body]

[optional footer(s)]
```

**Types:**

| type | use for |
|---|---|
| `feat` | a new feature |
| `fix` | a bug fix |
| `docs` | documentation only |
| `style` | formatting, whitespace, no code meaning change |
| `refactor` | code change that neither fixes a bug nor adds a feature |
| `perf` | a change that improves performance |
| `test` | adding or correcting tests |
| `build` | changes to the build system or dependencies |
| `ci` | changes to CI configuration/scripts |
| `chore` | everything else (tooling, repo maintenance) |
| `revert` | reverts a previous commit |

**Scope** is optional and names the affected area, e.g. `fix(auth): ...`.

**Breaking changes**: append `!` after the type/scope (`feat!: ...` or
`feat(api)!: ...`) and/or add a `BREAKING CHANGE:` footer describing the
impact and migration.

**Examples:**

```
feat(api): add pagination to the search endpoint
fix: handle empty input in the parser
docs: document the deployment steps
refactor(core)!: rename `process()` to `run()`

BREAKING CHANGE: callers must update `process()` calls to `run()`.
```

Keep the summary line imperative and under ~72 characters. Use the body to
explain *why*, not *what* — the diff already shows what changed.

## Pull requests

- Branch from the default branch; name branches `<type>/<short-description>`
  (e.g. `feat/search-pagination`).
- Keep PRs scoped to one logical change; split unrelated changes into
  separate PRs.
- Fill in the commands from `CLAUDE.md` (`## Commands`) locally before
  opening a PR — lint/test/build should pass.
- Reference any related issue in the PR description.
