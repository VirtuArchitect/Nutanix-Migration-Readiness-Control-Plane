# Publication Handoff

`publication-handoff` creates a local branch-owner handoff record from the
current publication and product-readiness artifacts. It does not stage, commit,
push, publish, or contact infrastructure.

Run the prerequisite checks first:

```powershell
$env:PYTHONPATH = "src"
python scripts\security_scan.py
python -m nmrcp.cli github-readiness `
  --repo-root . `
  --out outputs\github-publication-review.md `
  --json-out outputs\github-publication-review.json
python -m nmrcp.cli publication-staging-manifest `
  --repo-root . `
  --out outputs\publication-staging-manifest.md `
  --json-out outputs\publication-staging-manifest.json
python -m nmrcp.cli product-readiness `
  --repo-root . `
  --vault "C:\Users\john\OneDrive\09 Profile\Documents\OBSIDIAN VAULT GITS\Nutanix Migration & Readiness Control Plane" `
  --mvp-proof-package outputs\smoke-mvp-proof-package.zip `
  --github-publication-review outputs\github-publication-review.md `
  --github-publication-review-json outputs\github-publication-review.json `
  --publication-staging-manifest outputs\publication-staging-manifest.md `
  --publication-staging-manifest-json outputs\publication-staging-manifest.json `
  --out outputs\product-readiness-report.md `
  --json-out outputs\product-readiness-report.json
```

Capture smoke output to a durable log, then build the handoff:

```powershell
python -m nmrcp.cli publication-handoff `
  --repo-root . `
  --vault "C:\Users\john\OneDrive\09 Profile\Documents\OBSIDIAN VAULT GITS\Nutanix Migration & Readiness Control Plane" `
  --github-publication-review outputs\github-publication-review.md `
  --github-publication-review-json outputs\github-publication-review.json `
  --product-readiness-report outputs\product-readiness-report.md `
  --product-readiness-report-json outputs\product-readiness-report.json `
  --smoke-log outputs\smoke-product-readiness-report-validation.log `
  --security-scan-status pass `
  --out outputs\publication-handoff.md `
  --json-out outputs\publication-handoff.json
```

Validate the handoff before using it for branch-owner review:

```powershell
python -m nmrcp.cli validate-publication-handoff `
  --repo-root . `
  --vault "C:\Users\john\OneDrive\09 Profile\Documents\OBSIDIAN VAULT GITS\Nutanix Migration & Readiness Control Plane" `
  --github-publication-review outputs\github-publication-review.md `
  --github-publication-review-json outputs\github-publication-review.json `
  --product-readiness-report outputs\product-readiness-report.md `
  --product-readiness-report-json outputs\product-readiness-report.json `
  --smoke-log outputs\smoke-product-readiness-report-validation.log `
  --security-scan-status pass `
  --report outputs\publication-handoff.md `
  --json-report outputs\publication-handoff.json
```

The validator recomputes the handoff from the current inputs. It rejects stale
JSON, Markdown missing the current checks/actions/boundaries, invalid product
or GitHub readiness reports, missing smoke evidence, or a failed security scan
status.

`ready_for_branch_owner` means the local handoff record is current and can be
reviewed before staging. It is not an external-customer readiness claim. The
product remains blocked for external handoff until approved vCenter/Prism
endpoint evidence and approved Nutanix Move appliance proof are present.
