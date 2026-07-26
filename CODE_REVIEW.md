# Code Review Standard

Review code for correctness, regressions, maintainability, security, and test
coverage. For this product, security includes migration-safety behavior:
read-only collectors, dry-run Move artifacts, local-only credential handling,
and redacted evidence.

## Review Priorities

1. Bugs that break requested behavior or generated evidence contracts.
2. Security vulnerabilities, credential leakage, or mutation-path mistakes.
3. Data loss, data corruption, privacy risks, or unsafe migration guidance.
4. Missing tests for changed behavior.
5. Performance or reliability issues with realistic migration impact.
6. Maintainability issues that make future connector or evidence changes risky.

## Checklist

### Correctness

- Does the change satisfy the requested migration-readiness behavior?
- Are edge cases handled for malformed inventory, missing ownership, dependency
  gaps, held workloads, and unavailable endpoint data?
- Are public schemas and generated artifact names compatible?
- Do reviewers have enough evidence to understand why a workload is ready,
  held, blocked, or excluded from Move staging?

### Testing

- Are tests added or updated for changed behavior?
- Do tests cover success, failure, and boundary cases?
- Is the changed path covered by smoke, CI, or a documented manual gate?
- Are skipped tests or missing external lab checks explained?

### Security

- Are connectors still read-only unless mutation is explicitly approved?
- Are secrets kept in environment variables, prompts, or external stores rather
  than files, arguments, logs, or evidence packages?
- Are generated artifacts redacted or explicitly documented as sensitive?
- Are dry-run Move payloads still guarded by `dry_run_only: true` and
  `mutation_allowed: false`?
- Are dependency changes justified and reviewed?

### Maintainability

- Does the change follow local conventions?
- Is the code simpler than the problem requires?
- Are abstractions justified by real reuse or complexity reduction?
- Are comments useful and limited to non-obvious behavior?

## Review Output

When asked for a review, report findings first:

- Severity.
- File and line.
- Problem.
- Impact.
- Suggested fix.

Then include open questions, test gaps, and a brief summary. If no issues are
found, say so clearly and mention residual risk.
