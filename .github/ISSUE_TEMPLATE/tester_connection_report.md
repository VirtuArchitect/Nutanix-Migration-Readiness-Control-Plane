---
name: Tester Connection Report
about: Report approved lab connection, collection, and readiness results
title: "[Tester] Read-only connection and readiness result"
labels: tester-feedback
assignees: ""
---

## Safety Checklist

- [ ] I used an approved lab or explicitly approved source environment.
- [ ] I used read-only credentials.
- [ ] I removed credentials, endpoint values, FQDNs, IP addresses, customer
      identifiers, screenshots with sensitive values, and raw inventory.

## Runtime

- NMRCP commit or release:
- Runtime path: Docker Compose / Python / other approved path
- Browser and OS:

## Source Type

- vCenter tested: yes / no
- Prism Central tested: yes / no
- RVTools or offline import tested: yes / no
- Source label: redacted lab / simulator / sample data

## Workflow Result

- Test Read-only Connections: pass / fail / not run
- Collect Source Evidence: pass / fail / not run
- Run Readiness Assessment: pass / fail / not run

## Readiness Summary

- Workload count:
- Ready count:
- Blocked count:
- Top blocker categories:

## Expected Result

Describe what you expected to happen.

## Actual Result

Describe what happened and paste only redacted proof snippets.

## Redacted Evidence Attached

- [ ] `live-readiness.json`
- [ ] `collection-summary.json`
- [ ] `collection-proof-report.md`
- [ ] `assessment.json`
- [ ] `evidence-manifest.json`
- [ ] Other redacted artifact:
