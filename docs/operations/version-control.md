# Version Control

NMRCP uses explicit product versioning so operators and testers can identify
which console, CLI, and evidence workflow produced an artifact.

## Current Version

- Product version: `0.2.0`
- Source of truth: `pyproject.toml` and `src/nmrcp/__init__.py`
- Console visibility: generated operations consoles render the product version
  in the navigation rail and operations ribbon.
- CLI visibility: `python -m nmrcp.cli version`

## Version Rules

- Use semantic versioning: `MAJOR.MINOR.PATCH`.
- Increment `PATCH` for compatible fixes, documentation corrections, and small
  operational refinements.
- Increment `MINOR` for new operator workflows, connector capabilities, gates,
  or evidence artifacts that remain backward compatible.
- Increment `MAJOR` for breaking changes to evidence contracts, CLI command
  behavior, schema formats, or published operator workflows.

## Release Discipline

- Keep `pyproject.toml` and `src/nmrcp/__init__.py` at the same version.
- Regenerate `docs/demo/operations-console.html` when the console version or
  visible console identity changes.
- Tag GitHub releases as `vX.Y.Z` after tests, smoke, security scan, hosted CI,
  and hosted Pages validation pass.
- Do not place customer names, endpoint names, credentials, tokens, or generated
  output folders in version commits or tags.
