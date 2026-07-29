# Provider Model

NMRCP now uses a provider-aware architecture while preserving the current
validated VMware-to-Nutanix implementation.

## Naming

- **MRCP**: Migration Readiness Control Plane, the parent product architecture.
- **NMRCP**: Nutanix Provider Edition, the current implementation in this repo.

Do not present NMRCP as fully platform-agnostic until at least one additional
non-Nutanix target provider pair is implemented, tested, and documented.

## Current Validated Provider Pairs

| Source provider | Target provider | Rule set | Status |
| --- | --- | --- | --- |
| VMware vCenter | Nutanix AHV | VMware to Nutanix AHV | validated |
| VMware vCenter | Nutanix NC2 | VMware to Nutanix NC2 | validated |
| RVTools / Offline Import | Nutanix AHV | RVTools import to Nutanix AHV | validated |
| RVTools / Offline Import | Nutanix NC2 | RVTools import to Nutanix NC2 | validated |

## Architecture Boundary

The platform-agnostic part of MRCP is the governance core:

- redacted evidence schemas
- run metadata
- fail-closed validators
- evidence manifests and SHA-256 checks
- wave planning
- sign-off, rollback, risk, and handoff artifacts
- tester reports
- local-first console and Docker runtime

The platform-specific part stays in providers:

- source collectors
- target profiles
- source-to-target readiness rule sets
- compatibility guidance
- API proof and safety gates

## Implementation Rule

Generalise the framework, not the scoring heuristics. A future
VMware-to-Hyper-V rule set should not reuse Nutanix VirtIO or Prism-specific
rules. A future Hyper-V-to-AHV rule set should not pretend VMware Tools evidence
exists. Each source-target pair needs its own rule set and tests.

## Next Provider Milestone

The next technical milestone is to keep the existing provider pair active while
adding a second provider pair behind the same contracts. Good candidates are:

- VMware vCenter to Microsoft Hyper-V / Azure Local
- VMware vCenter to Proxmox VE

The second provider pair should be added only after read-only collection,
compatibility criteria, and evidence validation are defined from primary vendor
documentation or validated lab behavior.
