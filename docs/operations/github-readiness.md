# GitHub Readiness

The repository is prepared for branch-oriented development against
`VirtuArchitect/Nutanix-Migration-Readiness-Control-Plane`.

## Local Install

The project declares a zero-dependency console script:

```powershell
python -m pip install -e .
nmrcp doctor
```

`nmrcp` maps to `nmrcp.cli:main`. The documented `python -m nmrcp.cli`
commands remain valid for fresh clones that set `PYTHONPATH=src` without an
editable install.
`doctor` verifies the same console-script metadata and checks that generated
artifacts such as `outputs/`, editable-install `*.egg-info/`, `build/`, `dist/`,
and `.env` are ignored before publication or pull-request packaging.
On Windows, `pip` may install `nmrcp.exe` into the per-user Scripts directory
without adding that directory to `PATH`; locate it with:

```powershell
$scripts = python -c "import sysconfig; print(sysconfig.get_path('scripts', scheme='nt_user'))"
& (Join-Path $scripts 'nmrcp.exe') doctor --json
```

## Required Local Evidence

Run the same checks before opening a pull request:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli github-readiness `
  --repo-root . `
  --expected-remote https://github.com/VirtuArchitect/Nutanix-Migration-Readiness-Control-Plane `
  --out outputs\github-publication-review.md `
  --json-out outputs\github-publication-review.json
python -m nmrcp.cli validate-github-publication-review `
  --repo-root . `
  --expected-remote https://github.com/VirtuArchitect/Nutanix-Migration-Readiness-Control-Plane `
  --report outputs\github-publication-review.md `
  --json-report outputs\github-publication-review.json
Get-ChildItem src\nmrcp\*.py | ForEach-Object { python -m py_compile $_.FullName }
python -m unittest discover -s tests
python scripts\security_scan.py
powershell -ExecutionPolicy Bypass -File scripts\smoke.ps1
python scripts\security_scan.py
```

`github-readiness` distinguishes a populated local folder from a publishable
repository. It discovers the current publication surface from root project
files, `.github/`, `docs/`, `examples/`, `scripts/`, `src/nmrcp/`, and `tests/`
while excluding generated caches, `outputs/`, build artifacts,
editable-install metadata, and `.env`. It fails when any discovered publication
path is missing or not tracked by Git; when the readiness gate modules, tests,
or operation guides for `github-readiness`, `vault-readiness`, and
`product-readiness` are missing; when the `origin` remote does not point at
`VirtuArchitect/Nutanix-Migration-Readiness-Control-Plane`; or when forbidden
generated artifacts are tracked.
This keeps the MVP publication gate honest while branch commits and pushes
remain a human operator action. Hosted CI runs the same command immediately
after compile so a pull request cannot silently drop required publication files
or point at the wrong repository.
When required publication paths are present but untracked, the command prints a
reviewable `NEXT:` action with the exact `git add -- ...` command for required
paths, followed by a separate commit/push reminder. It never stages, commits,
pushes, or removes files on the operator's behalf.
When `--out` or `--json-out` is provided, the same local result is written as a
sanitized publication review artifact. The Markdown review records status,
checks, next actions, required publication paths, and operator boundaries so the
branch owner can review the staging set before commit or pull-request creation.
Run `validate-github-publication-review` against the Markdown and JSON outputs
before using them in a pull request or release checklist; it rejects stale JSON
fields and Markdown that no longer contains the current checks, next actions,
required paths, or operator boundary text. Hosted CI writes and validates the
same review artifacts immediately after `github-readiness`.

The hosted CI smoke also exercises the proof handoff path, not only the base
assessment path. It now generates and validates:

- assessment intake preflight with local-safety acknowledgements,
- redacted live endpoint proof from the simulated collector smoke,
- lab-scoped Move payload, capture kit, submit-readiness proof, transcript
  validation, simulated proof validation, and an isolated generated approved
  proof rehearsal with final evidence intake,
- final change-gate warning acceptance,
- handoff package verification with approval exceptions, operator review, and
  Move capture-kit evidence,
- MVP audit, MVP proof package, semantic `verify-mvp-proof`, proof summary,
  `validate-mvp-proof-summary`, MVP closure report, and
  `validate-mvp-closure-report`, with the validated Move lab runbook, source
  endpoint evidence request, Move lab evidence request, operator gate summary,
  and handoff package roles all carried into the proof zip,
- launch readiness report for partner/customer-facing review status, including
  final `validate-launch-readiness-report` and explicit CI checks that the
  generated JSON and Markdown still show
  `blocked_for_external_handoff` while approved Move proof is simulated.

This keeps GitHub pull requests aligned with the local `scripts\smoke.ps1`
proof posture while still marking real Nutanix Move appliance behavior as
unproven until an approved non-production lab run is captured.
The local PowerShell smoke runner is fail-fast for native `python` and nested
`powershell` exit codes; rerun it after changes that touch CLI, proof, evidence,
or packaging surfaces.
It also performs a final proof package, proof summary, closure report, and
launch readiness refresh after the Move lab workflow rehearsals so the smoke
artifacts left in `outputs/` validate against the final proof package.
The generated approved proof rehearsal uses synthetic CI transcript evidence to
prove the `generate-approved-move-lab-proof`, proof-validation, and
evidence-intake contracts. It is not packaged as final external handoff proof.

## Review Routing

`.github/CODEOWNERS` routes all repository changes to `@VirtuArchitect`, with
explicit ownership on connector, redaction, Move payload, lab proof, and security
documentation surfaces.

## Templates

- Bug reports ask for redacted evidence and migration scope.
- Feature requests ask whether endpoint credentials, production infrastructure,
  or mutation paths are involved.
- Security review issues track connector, evidence, Move payload, lab-proof,
  CI, and dependency changes.
- Pull requests include compile, unit, security scan, smoke, redaction, dry-run
  Move payload, MVP proof package, closure report, launch readiness report, and
  residual-risk checkboxes.

## Publication Notes

Do not push raw customer exports, support bundles, credentials, generated
`outputs/`, or lab appliance identifiers. The MVP may publish partial proof
packages for review, but approved Nutanix Move appliance behavior remains
unproven until an authorized non-production lab round trip is captured and
validated.
