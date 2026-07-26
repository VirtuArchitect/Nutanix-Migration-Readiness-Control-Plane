# Move Lab Transcript

`validate-move-lab-transcript` validates a redacted transcript from a real
non-production Nutanix Move appliance API round trip. It is designed to sit
between the lab runbook and the final approved Move lab proof.

The transcript must not contain endpoint URLs, headers, request bodies, response
bodies, tokens, cookies, passwords, or authorization values. Store only relative
API paths, status codes, redaction flags, dry-run flags, mutation flags, and
optional request/response body hashes.

## Command

```powershell
$payload = "outputs\sample-assessment\move-api-payload.lab.dry-run.json"
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $payload).Hash.ToLowerInvariant()

# Add $hash to the transcript as payload_sha256 after the lab operator reviews
# the dry-run payload file.
$env:NMRCP_MOVE_LAB_ACK = "I_UNDERSTAND_LAB_ONLY"
python -m nmrcp.cli validate-move-lab-transcript `
  --transcript outputs\move-lab-transcript.approved.json `
  --payload $payload `
  --review examples\sample_move_submit_review.json `
  --out outputs\move-lab-transcript-validation.json
Remove-Item Env:\NMRCP_MOVE_LAB_ACK
```

Generate a capture kit before the lab window so the operator has a redacted
template and checklist:

```powershell
$env:NMRCP_MOVE_LAB_ACK = "I_UNDERSTAND_LAB_ONLY"
python -m nmrcp.cli generate-move-lab-capture-kit `
  --payload outputs\sample-assessment\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --out-dir outputs\move-lab-capture-kit
python -m nmrcp.cli validate-move-lab-capture-kit `
  --kit-dir outputs\move-lab-capture-kit `
  --payload outputs\sample-assessment\move-api-payload.lab.dry-run.json `
  --out outputs\move-lab-capture-kit-validation.json
Remove-Item Env:\NMRCP_MOVE_LAB_ACK
```

The generated `move-lab-transcript.template.json` intentionally uses
`evidence_state=template_only_replace_after_lab_capture`; it will not pass
validation until the operator copies it to an approved transcript, replaces the
template-only values with redacted lab evidence, and sets
`evidence_state=captured_approved_lab`.

`validate-move-lab-capture-kit` verifies the template/checklist pair before the
lab window. It checks redaction, the reviewed payload SHA-256, template-only
state, lab-only flags, zero pre-capture result counters, and the checklist text
needed to capture approved evidence safely. The generated checklist also carries
the `generate-approved-move-lab-proof` command so operators derive the proof
hash/count fields from the cleaned transcript validation, plus the final
`validate-move-lab-evidence-intake` command so operators can turn the captured
transcript, transcript validation, proof validation, and capture-kit validation
into the `nmrcp_move_lab_evidence_intake_v1` artifact required for external
handoff.

## Transcript Contract

```json
{
  "schema_version": "nmrcp_move_lab_transcript_v1",
  "proof_scope": "approved_lab_move_appliance",
  "evidence_state": "captured_approved_lab",
  "environment": "lab",
  "lab_move_appliance": "move-lab-01",
  "payload_sha256": "<sha256 of reviewed dry-run payload>",
  "dry_run_only": true,
  "mutation_performed": false,
  "production_targets": false,
  "interactions": [
    {
      "name": "create-reviewed-dry-run-plan",
      "method": "POST",
      "path": "/api/move/lab/dry-run-plans",
      "status_code": 202,
      "dry_run": true,
      "mutating": false,
      "redacted": true,
      "request_sha256": "<optional redacted request body hash>",
      "response_sha256": "<optional redacted response body hash>"
    }
  ],
  "results": {
    "accepted_payloads": 1,
    "created_plans": 1,
    "started_migrations": 0
  }
}
```

## Gate Behavior

The validator fails closed when:

- the transcript is not `approved_lab_move_appliance` scope.
- `payload_sha256` does not match the reviewed dry-run payload file.
- the environment is not `lab`.
- the transcript still has template-only `evidence_state`.
- mutation or production-target flags are true.
- no `dry_run=true` POST interaction is present.
- any interaction stores raw URLs, headers, bodies, cookies, tokens, passwords,
  authorization values, or secret-like text.
- any interaction reports a non-2xx status code or a mutating HTTP method.
- accepted payload count does not cover the reviewed payload workloads.
- started migration count is not zero.

Missing request or response hashes are warnings, not failures, because some lab
runs may only permit screenshot/log evidence. Supplying hashes is preferred for
review traceability.

## Safety

This command still does not submit anything to Nutanix Move. It validates
operator-captured evidence from an already approved lab run. Final MVP proof
still requires an approved `nmrcp_move_lab_proof_v1` file whose
`transcript_validation_sha256` matches this validation file, plus passing
`validate-move-lab-proof` output with `approved_lab_move_appliance` scope.
