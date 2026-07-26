# Operator Assessment Review

`operator-review.csv` records the human review step between generated evidence
and change-board handoff. It is intentionally separate from automated checks:
the control plane can prove hashes, redaction, Move-plan structure, and closure
trackers, but a migration lead still has to confirm that the package was
reviewed and accepted.

## Generate

Generate a draft template from an assessment directory:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli generate-operator-review `
  --dir outputs\sample-assessment `
  --out outputs\sample-operator-review.csv
```

The generated row uses schema `nmrcp_operator_review_v1` and starts as
`review_status=draft`. Required review fields are set to `no`; optional context
fields are set to `no` when the matching artifact exists or `not_applicable`
when it does not.

## Validate

Draft review:

```powershell
python -m nmrcp.cli validate-operator-review `
  --review outputs\sample-operator-review.csv `
  --allow-draft
```

Final review:

```powershell
python -m nmrcp.cli validate-operator-review `
  --review examples\sample_operator_review_approved.csv
```

An approved review must include reviewer, timestamp, change reference, notes,
and `yes` for coverage, readiness, Move plan, evidence, redaction, and rollback
review fields. Optional context fields accept `yes`, `no`, or
`not_applicable`; `no` is reported as a warning so reviewers can see what was
not evaluated.

When an approved review is supplied to `change-gate`, `summarize-gates`,
`package-handoff`, `run-assessment`, or `mvp-audit`, the `assessment_dir` value
must match the assessment directory being gated. Relative paths such as
`outputs/smoke` are accepted when they match the tail of the local assessment
path. This prevents reusing a stale review row from a different assessment
package.

## Gates

Pass the approved review into final gates and handoff packaging:

```powershell
python -m nmrcp.cli change-gate `
  --dir outputs\sample-assessment `
  --operator-review examples\sample_operator_review_approved.csv

python -m nmrcp.cli package-handoff `
  --dir outputs\sample-assessment `
  --operator-review examples\sample_operator_review_approved.csv `
  --out outputs\sample-handoff-package.zip
```

`change-gate` warns when no review is provided. When a review is provided, it
must pass validation unless `--allow-draft-operator-review` is explicitly used
for draft checks. `package-handoff` always requires an approved review before it
archives `review/operator-review.csv`.
