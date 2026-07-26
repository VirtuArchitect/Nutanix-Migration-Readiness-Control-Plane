# Tester Quickstart

This quickstart is for approved lab testers who need to prove the console can
connect, collect read-only source evidence, and generate readiness output.

## Safety Rules

- Use lab or explicitly approved source environments only.
- Use read-only vCenter and Prism Central accounts.
- Do not paste credentials, endpoint names, FQDNs, IP addresses, or customer
  identifiers into GitHub issues.
- Treat generated files as local evidence. Redact before sharing outside the
  approved test group.
- NMRCP does not execute migrations. Nutanix Move execution remains an approved
  lab-only handoff path.

## Docker Path

From the repository root:

```powershell
docker compose up --build
```

Open:

```text
http://localhost:8080/
```

Then run the browser workflow:

1. Enter approved vCenter and Prism Central connection details.
2. Select **Test Read-only Connections**.
3. Select **Collect Source Evidence** after the connection proof passes.
4. Select **Run Readiness Assessment** to score the collected inventory.
5. Select **Prepare Tester Report** to summarize the local redacted artifacts
   for GitHub feedback.
6. Review blocked workloads, findings, waves, and generated evidence paths.

The container writes runtime artifacts under the Compose-mounted `data`
directory. The main files testers should inspect are:

- `live-readiness.json`
- `source-collection/collection-summary.json`
- `source-collection/collection-proof-report.md`
- `assessment/assessment.json`
- `assessment/evidence-manifest.json`
- `assessment/operations-console.html`
- `tester-report.md`
- `tester-report.json`

## Python Path

Use this path when Docker is not available:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli serve --host 127.0.0.1 --port 8080 --site-dir outputs\console-site
```

Open:

```text
http://localhost:8080/
```

The same tester workflow applies. Runtime artifacts are written under the local
console data directory and assessment output directory.

To prepare the same report from the CLI:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli tester-report `
  --data-dir outputs\console-site\data `
  --out outputs\tester-report.md `
  --json-out outputs\tester-report.json
```

The command returns success only when the expected connection proof, source
collection proof, and readiness assessment artifacts are present and passing.

## What To Report

Open a **Tester Connection Report** issue and include:

- Commit SHA or release tag tested.
- Runtime path: Docker Compose or Python.
- Source type tested: vCenter, Prism Central, RVTools import, or sample data.
- Whether connection proof, collection, and readiness assessment passed.
- Counts from redacted summaries: workload count, ready count, blocked count,
  and top blocker categories.
- `tester-report.md` or redacted snippets from `tester-report.json`.
- Redacted snippets from proof or assessment files when they explain the issue.

Do not attach raw credentials, screenshots showing endpoint values, customer
names, FQDNs, IP addresses, VM names, or unredacted inventory.

## Expected MVP Outcome

A meaningful tester result should be able to say:

```text
I connected my lab with read-only accounts, collected source evidence, generated
readiness output, and the blocked/ready findings matched what I expected.
```
