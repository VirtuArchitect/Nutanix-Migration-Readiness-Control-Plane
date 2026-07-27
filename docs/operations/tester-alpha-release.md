# Tester Alpha Release

NMRCP `0.2.0` is the first tester-alpha release shape. The goal is to let an
approved tester say:

```text
I opened the local console, selected my environment, connected approved source
systems, collected read-only evidence, generated readiness output, and the
blockers matched my lab.
```

## What This Release Is For

- Connect approved lab or customer environments from a local served console.
- Test read-only vCenter and Prism Central reachability.
- Collect source inventory and target capacity evidence where approved.
- Analyze AHV and NC2 readiness from collected or imported inventory.
- Validate Dev, UAT, and Production gates before read or write-intent workflows.
- Prepare redacted tester feedback artifacts for GitHub issues.
- Package versioned assessment evidence with a run ID and NMRCP version.

## Runtime Options

- Static GitHub Pages demo: preview only, generated from sample inventory.
- Python served console: local API server that can connect to approved
  environments.
- Docker Compose console: same served console inside a local container.
- GHCR image: published by the `Publish Docker image` workflow for tags and
  manual alpha builds.

## Connectivity Boundary

The local served console and Docker console can initiate approved connectivity
tests and read-only collection against vCenter and Prism Central. Nutanix Move,
AHV, NC2, and ESXi workflows are represented through explicit environment
gates, dry-run or proof capture, and evidence handoff boundaries until a
connector-specific implementation is present and reviewed.

The static GitHub Pages demo cannot connect to infrastructure because it is a
browser-only preview without the local API server.

## Release Checklist

1. Confirm `pyproject.toml` and `src/nmrcp/__init__.py` use the same version.
2. Regenerate `docs/demo/operations-console.html`.
3. Run compile, unit tests, security scan, Docker smoke, and local smoke.
4. Confirm the direct demo URL serves the expected console version.
5. Create a Git tag such as `v0.2.0`.
6. Let the Docker publish workflow push:
   `ghcr.io/virtuarchitect/nutanix-migration-readiness-control-plane:0.2.0`.
7. Create a GitHub release with tester scope, known limits, security boundaries,
   and the direct console demo link.

## Evidence Versioning

Every assessment writes `run_metadata` into `assessment.json` with:

- schema version
- generated run ID
- generated timestamp
- `product_version`
- workflow name
- redacted source system
- workload and wave counts
- credential serialization policy
- mutation policy

Use the run ID, product version, and commit or release tag in tester feedback.
