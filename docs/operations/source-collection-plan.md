# Source Collection Plan

`source-collection-plan` turns a completed assessment intake into a
credential-safe operator brief before approved live collection starts. It is a
planning artifact, not endpoint proof.

```powershell
python -m nmrcp.cli source-collection-plan `
  --intake outputs\assessment-intake.csv `
  --out outputs\source-collection-plan.md
python -m nmrcp.cli validate-source-collection-plan `
  --plan outputs\source-collection-plan.md `
  --intake outputs\assessment-intake.csv
```

The generated plan records:

- the approved customer, partner, or MSP assessment scope from the intake,
- local-only handling rules for vCenter and Prism Central endpoint values,
  usernames, passwords, tokens, API keys, FQDNs, and IP addresses,
- the read-only collection sequence for `live-readiness`, `collect-sources`,
  and `validate-live-proof`,
- the required proof outputs for external live endpoint closeout,
- stop conditions for incomplete intake, leaked endpoint or secret material,
  mutation attempts, TLS exceptions, and failed proof validation.

The validator re-renders the expected plan from the intake and fails closed if
the Markdown drifts, omits the privacy posture, or contains endpoint or
secret-like material. The required privacy markers are
`credentials_serialized=false` and `endpoint_values_serialized=false`.

Use this artifact when an operator needs a safe customer-facing or
partner-facing checklist before live access is approved. Use
`live-readiness`, `collect-sources`, and `validate-live-proof` to produce the
actual proof after the approved collection window opens.
