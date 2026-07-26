# Product Readiness

`product-readiness` runs the top-level completion gates for the Nutanix
Migration & Readiness Control Plane.

Run it from the repository root:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli product-readiness `
  --repo-root . `
  --vault "C:\Users\john\OneDrive\09 Profile\Documents\OBSIDIAN VAULT GITS\Nutanix Migration & Readiness Control Plane" `
  --expected-remote https://github.com/VirtuArchitect/Nutanix-Migration-Readiness-Control-Plane `
  --assessment-dir outputs\workflow-assessment `
  --assessment-intake examples\sample_assessment_intake.csv `
  --live-proof outputs\source-collection\live-proof-validation.json `
  --move-proof outputs\move-lab-proof-validation.json `
  --move-lab-evidence-intake outputs\move-lab-evidence-intake.json `
  --mvp-proof-package outputs\smoke-mvp-proof-package.zip `
  --github-publication-review outputs\github-publication-review.md `
  --github-publication-review-json outputs\github-publication-review.json `
  --publication-staging-manifest outputs\publication-staging-manifest.md `
  --publication-staging-manifest-json outputs\publication-staging-manifest.json `
  --out outputs\product-readiness-report.md `
  --json-out outputs\product-readiness-report.json
```

The command aggregates:

- `mvp-audit`: local MVP implementation evidence and external proof gaps.
- `github-readiness`: GitHub publication and tracked-path readiness.
- `vault-readiness`: Obsidian documentation coverage.
- `mvp-proof-package`: optional semantic validation of the proof zip reviewers
  consume when `--mvp-proof-package` is supplied.
- `github-publication-review`: optional validation of generated publication
  review Markdown and JSON when those paths are supplied.
- `publication-staging-manifest`: optional validation of the hash-backed
  staging manifest when those paths are supplied.

The gate fails if any required local gate fails, returns partial when local
implementation exists but external proof is still open, and prints next actions
for the remaining blockers. It does not commit, push, contact vCenter/Prism, or
invent Nutanix Move evidence.
For GitHub publication blockers, those next actions include the concrete
reviewed `git add -- ...` command emitted by `github-readiness` plus a reminder
to commit and push only after operator approval.
Generate `outputs\github-publication-review.md` and
`outputs\github-publication-review.json` with `github-readiness --out
outputs\github-publication-review.md --json-out
outputs\github-publication-review.json` when the branch owner needs a durable
local review record before staging.
Validate those files with `validate-github-publication-review --report
outputs\github-publication-review.md --json-report
outputs\github-publication-review.json` before treating the review as current.

All `mvp-audit` proof inputs are accepted by `product-readiness`, including
assessment, intake, live proof, approved Move proof, evidence bundle, validation
results, remediation tracker, sign-offs, approval exceptions, operator review,
capture-kit validation, Move lab evidence intake, and warning acceptance. This
lets the aggregate gate move from partial to pass when real approved evidence is
available instead of hard-coding the MVP gate as partial.
The publication review Markdown and JSON paths are also accepted so a current
branch-owner publication review can be validated in the same aggregate command.
The publication staging manifest Markdown and JSON paths are accepted for the
same reason: the aggregate report can prove that the exact operator-reviewed
staging command and hashes still match the current worktree before branch-owner
handoff.
When `--mvp-proof-package` is supplied, the aggregate gate runs the same
`verify-mvp-proof` semantic checks against the packaged zip. This proves the
handoff artifact still carries valid proof roles, hashes, and role contracts
instead of only checking the loose source files used to build it.

When durable aggregate evidence is needed, write both report files and validate
them before using the result in a handoff:

```powershell
python -m nmrcp.cli validate-product-readiness-report `
  --repo-root . `
  --vault "C:\Users\john\OneDrive\09 Profile\Documents\OBSIDIAN VAULT GITS\Nutanix Migration & Readiness Control Plane" `
  --expected-remote https://github.com/VirtuArchitect/Nutanix-Migration-Readiness-Control-Plane `
  --github-publication-review outputs\github-publication-review.md `
  --github-publication-review-json outputs\github-publication-review.json `
  --publication-staging-manifest outputs\publication-staging-manifest.md `
  --publication-staging-manifest-json outputs\publication-staging-manifest.json `
  --mvp-proof-package outputs\smoke-mvp-proof-package.zip `
  --report outputs\product-readiness-report.md `
  --json-report outputs\product-readiness-report.json
```

The validator recomputes the current aggregate gate and rejects stale JSON or
Markdown that no longer contains the current gate summaries, blockers, next
actions, and completion boundary.

Use it before deciding whether the active product goal is truly complete. A
passing vault gate and passing local tests are not enough if the GitHub
publication gate or approved Move appliance proof gate is still open.
