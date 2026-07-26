# Readiness Policy

Readiness policy lets operators tune deterministic thresholds without changing
code. The policy is local JSON and is recorded in `assessment.json` so evidence
reviewers can see which thresholds were used.

## Example

```json
{
  "snapshot_max_age_days": 7,
  "backup_max_age_hours": 24,
  "prepare_risk_threshold": 25,
  "blocked_risk_threshold": 50
}
```

Run assessment with a policy:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli assess `
  --inventory examples\sample_inventory.json `
  --policy examples\sample_readiness_policy.json `
  --out outputs\policy-assessment
```

## Validation

- Unknown policy keys fail closed.
- Values must be positive integers.
- `prepare_risk_threshold` must be lower than `blocked_risk_threshold`.

## Operator Guidance

Use stricter thresholds for regulated or executive-visible migrations. Use more
relaxed thresholds only with explicit migration governance approval, and keep
the policy file with the change evidence.
