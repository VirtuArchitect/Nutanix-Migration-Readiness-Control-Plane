---
name: Security review
about: Track a defensive security review or safety-sensitive product change
title: "[Security Review]: "
labels: security
assignees: ""
---

## Scope


## Trigger

- [ ] Connector authentication/session behavior
- [ ] Endpoint path or HTTP method changes
- [ ] Customer inventory parsing
- [ ] Evidence export, redaction, or handoff packaging
- [ ] File handling
- [ ] Dry-run Move payload or lab-proof workflow
- [ ] CI, packaging, or release process
- [ ] Dependency or build change

## Safety Checklist

- [ ] No credentials, tokens, support bundles, or raw customer exports attached.
- [ ] Connectors remain read-only unless mutation is explicitly scoped and approved.
- [ ] Generated artifacts do not include endpoint URLs, usernames, passwords, or secrets.
- [ ] Dry-run Move payloads keep `dry_run_only: true` and `mutation_allowed: false`.
- [ ] Redaction review and security scan commands are documented.
- [ ] Residual risk is documented.

## Findings


## Follow-Up


