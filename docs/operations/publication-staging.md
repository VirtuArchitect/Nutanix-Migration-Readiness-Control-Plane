# Publication Staging Manifest

`publication-staging-manifest` creates a non-mutating staging review file for
the required GitHub publication paths. The path set is discovered from the
current repo surface: root project files, `.github/`, `docs/`, `examples/`,
`scripts/`, `src/nmrcp/`, and `tests/`, excluding generated caches, `outputs/`,
build artifacts, editable-install metadata, and `.env`. It lists every required
file, whether it is already tracked, its byte size, SHA-256 hash, local
forbidden-to-stage candidates, and the exact `git add -- ...` command for
operator review.

Generate the manifest after the publication and product-readiness reports are
current:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli publication-staging-manifest `
  --repo-root . `
  --out outputs\publication-staging-manifest.md `
  --json-out outputs\publication-staging-manifest.json
```

Validate it before running any Git staging command:

```powershell
python -m nmrcp.cli validate-publication-staging-manifest `
  --repo-root . `
  --report outputs\publication-staging-manifest.md `
  --json-report outputs\publication-staging-manifest.json
```

The validator recomputes the manifest from the current files. It rejects stale
JSON, Markdown missing the current hashes or operator boundaries, and missing
required publication paths.

`ready_for_operator_staging` means the manifest is current and every required
publication path exists. It does not stage files. Review the hashes, confirm
`outputs/` and other forbidden candidates are not included, then run the printed
`git add -- ...` command only after operator approval.

After staging, rerun:

```powershell
python -m unittest discover -s tests
python scripts\security_scan.py
powershell -ExecutionPolicy Bypass -File scripts\smoke.ps1
python -m nmrcp.cli github-readiness --repo-root .
python -m nmrcp.cli product-readiness --repo-root . `
  --vault "C:\Users\john\OneDrive\09 Profile\Documents\OBSIDIAN VAULT GITS\Nutanix Migration & Readiness Control Plane"
```

Do not claim external handoff readiness until approved vCenter/Prism evidence
and approved Nutanix Move appliance proof are present.
