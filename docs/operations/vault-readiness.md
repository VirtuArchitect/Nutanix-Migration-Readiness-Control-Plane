# Vault Readiness

`vault-readiness` checks that the Obsidian vault mirrors the repository
operation guides and that the vault index links to each required note.

Run it from the repository root:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli vault-readiness `
  --repo-root . `
  --vault "C:\Users\john\OneDrive\09 Profile\Documents\OBSIDIAN VAULT GITS\Nutanix Migration & Readiness Control Plane"
```

The command validates:

- `docs/operations/*.md` coverage.
- required vault notes such as `README.md`, `Implementation Log.md`,
  `Architecture.md`, `Security Model.md`, and `GitHub Readiness.md`.
- expected operation-note mirrors, including deliberate naming differences such
  as `metadata-enrichment.md` to `Workload Metadata Enrichment.md`.
- nonempty note content.
- vault `README.md` wiki links for every expected note.

Use this before claiming that implementation work is fully documented in the
vault. It does not commit or push either repository; it only proves local
documentation coverage.
