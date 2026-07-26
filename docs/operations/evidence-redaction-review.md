# Evidence Redaction Review

`review-evidence` scans generated assessment evidence for unredacted sensitive
patterns before the package is shared.

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli review-evidence --dir outputs\sample-assessment
```

The review checks text artifacts listed in `evidence-manifest.json`, plus the
manifest itself, for:

- raw URLs.
- email addresses.
- IPv4 addresses.
- common internal hostnames.
- secret-like assignments.

Generated redaction markers such as `[REDACTED_URL]` are accepted. Any finding
fails the command and should be corrected before packaging or handoff.

Collection audit metadata is expected in assessment evidence. It should expose
only schema, mode, read-only path names, collection limits, observed counts, and
mutation posture. The review should fail if audit text reintroduces raw endpoint
URLs, usernames, passwords, or secret-like assignments.

`change-gate` and `run-assessment` run the same review automatically. This is a
defense-in-depth check; it does not replace human review because workload names,
owners, dependency names, and business context may still be sensitive even when
they do not match a redaction pattern.

Evidence bundles are also closed against their manifest: `verify-evidence
--bundle` rejects archive entries that are not listed in
`evidence-manifest.json`, so manually added files cannot bypass redaction and
integrity review by riding alongside the reviewed artifacts.
