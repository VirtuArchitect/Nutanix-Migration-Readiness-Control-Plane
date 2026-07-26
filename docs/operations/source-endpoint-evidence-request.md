# Source Endpoint Evidence Request

`source-endpoint-evidence-request.md` is generated with every assessment. It is
the operator or partner request for an approved read-only vCenter and Prism
Central validation window.

The request is intentionally not proof. It scopes the endpoint validation window,
read-only calls, local credential handling, collection artifacts, live proof
closeout commands, and stop conditions needed before live endpoint proof can be
trusted.

## Validate

```powershell
python -m nmrcp.cli validate-source-endpoint-evidence-request `
  --request outputs\sample-assessment\source-endpoint-evidence-request.md
```

`change-gate` and handoff package verification run the same validation.

## Required Content

The validator requires:

- vCenter and Prism Central scope.
- read-only posture.
- `mutating_calls=0`.
- `credentials_serialized=false`.
- `endpoint_values_serialized=false`.
- `live-readiness`.
- `assessment-intake`.
- `validate-assessment-intake`.
- `collect-sources`.
- `--assessment-intake`.
- `validate-live-proof`.
- `--require-vcenter`.
- `--require-prism`.
- `nmrcp_live_endpoint_proof_v1`.

Use this artifact before the live validation window. Use `validate-live-proof`
after approved collection to produce the actual endpoint proof.
