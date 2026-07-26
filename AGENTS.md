# AGENTS.md

## Repository Instructions

This repository expects production-grade engineering by default. Follow these
instructions for all code changes in this repo.

## Project Commands

```text
Install: no runtime install required for MVP; use Python 3.11+ and PYTHONPATH=src
Lint: Get-ChildItem src/nmrcp/*.py | ForEach-Object { python -m py_compile $_.FullName }
Format check: not configured
Type check: not configured
Unit tests: python -m unittest discover -s tests
Integration tests: not configured
End-to-end tests: not configured
Build: not configured
Run app: python -m nmrcp.cli assess --inventory examples/sample_inventory.json --out outputs/sample-assessment
Smoke test: powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1
Security scan: manual review with SECURITY_REVIEW.md; ensure no secrets in outputs
```

## Project Context

- The product is a local-first Nutanix migration readiness and evidence control
  plane for VMware-to-AHV/NC2 migration planning.
- Keep collectors read-only by default.
- Keep secrets local. Never persist vCenter, Prism Central, or customer
  credentials in repository files, logs, or evidence packs.
- Prefer deterministic, explainable readiness rules over opaque scoring.
- Treat customer inventory as sensitive data. Redact evidence artifacts unless
  the user explicitly chooses otherwise.
- Do not introduce new runtime dependencies without asking first.

## Definition of Done

Work is not complete until:

- The requested change is implemented.
- Relevant tests are added or updated, or the reason for not adding tests is
  explained.
- Relevant automated checks are run.
- A smoke test verifies the changed path.
- Security-sensitive changes receive a security review.
- Remaining risks or skipped checks are documented.

## Required Checks

Use the commands defined above. Recommended order:

1. Fast targeted unit tests for changed scoring, export, or connector behavior.
2. `Get-ChildItem src/nmrcp/*.py | ForEach-Object { python -m py_compile $_.FullName }`.
3. `python -m unittest discover -s tests`.
4. `powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1`.

## Security Review Trigger

Perform a security review when touching:

- vCenter or Prism Central authentication.
- Connector HTTP behavior, TLS, sessions, tokens, or credential handling.
- Redaction, evidence exports, logs, or filesystem paths.
- Customer inventory parsing or generated artifacts.
- CI/CD or packaging.
