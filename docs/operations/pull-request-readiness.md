# Pull Request Readiness

`pull-request-readiness` creates a local branch-owner packet from the current
GitHub publication review, product-readiness report, publication handoff,
publication staging manifest, smoke log, and security-scan result.

Generate it after the prerequisite artifacts validate:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli pull-request-readiness `
  --repo-root . `
  --vault "C:\Users\john\OneDrive\09 Profile\Documents\OBSIDIAN VAULT GITS\Nutanix Migration & Readiness Control Plane" `
  --github-publication-review outputs\github-publication-review.md `
  --github-publication-review-json outputs\github-publication-review.json `
  --product-readiness-report outputs\product-readiness-report.md `
  --product-readiness-report-json outputs\product-readiness-report.json `
  --publication-handoff outputs\publication-handoff.md `
  --publication-handoff-json outputs\publication-handoff.json `
  --publication-staging-manifest outputs\publication-staging-manifest.md `
  --publication-staging-manifest-json outputs\publication-staging-manifest.json `
  --smoke-log outputs\smoke-pull-request-readiness.log `
  --security-scan-status pass `
  --out outputs\pull-request-readiness.md `
  --json-out outputs\pull-request-readiness.json
```

Validate before using it for branch-owner review:

```powershell
python -m nmrcp.cli validate-pull-request-readiness `
  --repo-root . `
  --vault "C:\Users\john\OneDrive\09 Profile\Documents\OBSIDIAN VAULT GITS\Nutanix Migration & Readiness Control Plane" `
  --github-publication-review outputs\github-publication-review.md `
  --github-publication-review-json outputs\github-publication-review.json `
  --product-readiness-report outputs\product-readiness-report.md `
  --product-readiness-report-json outputs\product-readiness-report.json `
  --publication-handoff outputs\publication-handoff.md `
  --publication-handoff-json outputs\publication-handoff.json `
  --publication-staging-manifest outputs\publication-staging-manifest.md `
  --publication-staging-manifest-json outputs\publication-staging-manifest.json `
  --smoke-log outputs\smoke-pull-request-readiness.log `
  --security-scan-status pass `
  --report outputs\pull-request-readiness.md `
  --json-report outputs\pull-request-readiness.json
```

`ready_after_operator_staging` means the local PR packet is current and can be
reviewed before operator-controlled staging. It does not stage, commit, push,
publish, open a pull request, or mutate infrastructure.

After operator-approved staging, rerun full tests, security scan, smoke,
`github-readiness`, `product-readiness`, and this packet before opening a pull
request. External handoff remains blocked until approved endpoint evidence and
approved Nutanix Move appliance proof are present.
