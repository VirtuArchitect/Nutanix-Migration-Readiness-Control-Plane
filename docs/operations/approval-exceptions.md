# Approval Exceptions

`approval-exceptions.csv` is generated with every assessment. It makes formal
risk acceptance and exception approval work explicit for held workloads,
high-risk workloads, and high or critical readiness findings.

Validate it with:

```powershell
python -m nmrcp.cli validate-approval-exceptions `
  --exceptions outputs\sample-assessment\approval-exceptions.csv `
  --assessment outputs\sample-assessment\assessment.json
```

The validator compares the CSV to the `nmrcp_approval_exceptions_v1` context
embedded in `assessment.json`. `change-gate` runs the same contract
automatically.

Validate a filled final exception register with:

```powershell
python -m nmrcp.cli validate-approval-exception-approvals `
  --exceptions examples\sample_approval_exceptions_approved.csv `
  --assessment outputs\sample-assessment\assessment.json
```

The final validator checks that every generated exception row is still present,
that no extra exception rows were added, and that non-closure fields still match
`assessment.json`. For final closure, every row must be `approved` or `waived`
with `approval_ref`, `approved_by`, and `approved_at`; `required` is allowed
only with `--allow-required` during draft review, and `rejected` always blocks
closure.

Columns:

- `schema_version`: `nmrcp_approval_exceptions_v1`.
- `exception_id`: stable workload/type/finding key.
- `workload_id`, `name`, `owner`, `target`, `wave`: workload context.
- `readiness`, `risk_score`: readiness posture that triggered review.
- `exception_type`: `readiness_exception`, `high_risk_exception`, or
  `finding_exception`.
- `finding_code`, `severity`: exception source.
- `required_approval`: required approval roles.
- `approval_status`: generated as `required` until external approval evidence
  is attached.
- `blocking_reason`, `required_action`: change-board action and stop condition.
- `evidence_refs`: related artifacts for reviewer traceability.
- `approval_ref`, `approved_by`, `approved_at`, `notes`: final closure fields
  filled from the approved change-board or risk-acceptance record.

Operational use:

- Treat every row as unresolved until approval evidence is attached outside the
  generated baseline.
- Use the register alongside `owner-signoff-matrix.csv` and
  `remediation-tracker.csv` during final change-board review.
- Pass the filled final register to `change-gate --approval-exceptions`,
  `summarize-gates --approval-exceptions`, `package-handoff
  --approval-exceptions`, or `run-assessment --approval-exceptions` so closure
  is validated and archived.
- Do not use the generated `required` status as proof of approval.
