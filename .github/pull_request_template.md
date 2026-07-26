## Summary

- 

## Verification

- [ ] Python compile check
- [ ] `python scripts/security_scan.py`
- [ ] `PYTHONPATH=src python -m unittest discover -s tests`
- [ ] `powershell -ExecutionPolicy Bypass -File scripts\smoke.ps1`
- [ ] Generated or changed evidence artifacts reviewed

## Security

- [ ] No credentials or customer exports committed
- [ ] Connector changes are read-only or explicitly approved
- [ ] Evidence redaction impact reviewed
- [ ] Dry-run Move payloads still set `dry_run_only: true`
- [ ] Dry-run Move payloads still set `mutation_allowed: false`
- [ ] Lab-only or external-proof gaps are documented

## Residual Risk

- 
