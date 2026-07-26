# Docker Console

The Docker image runs the local operations console without requiring Python on
the operator workstation.

Build and run with Compose:

```powershell
docker compose up --build
```

Open:

```text
http://localhost:8080/
```

Tester workflow:

1. Open the console and enter approved lab vCenter and Prism Central endpoint
   details.
2. Select **Test Read-only Connections** to run the redacted
   `/api/connection-test` proof. The proof is written locally as
   `live-readiness.json` under the console data directory.
3. Select **Collect Source Evidence** to run the read-only collector through
   `/api/collect-sources`. This writes local `vcenter-inventory.json`,
   `vcenter-networks.json`, `prism-inventory.json`, `prism-capacity.json`,
   `collection-summary.json`, and the collection proof report.
4. Select **Run Readiness Assessment** to score the collected inventory through
   `/api/run-readiness` and refresh the operations console with the tester's
   readiness output.
5. Select **Prepare Tester Report** to run `/api/tester-report` and write local
   `tester-report.md` and `tester-report.json` files for redacted GitHub
   feedback.

Health endpoint:

```text
http://localhost:8080/healthz
```

The container writes the generated console site under `/data/console-site`.
With the included Compose file, that maps to `.\data` on the host. Runtime
connection proofs and generated assessment artifacts are local-only runtime
outputs and are not intended for source control.

The image does not contact vCenter, Prism Central, Nutanix Move, AHV, or NC2 by
itself. Live endpoint testing and collection require explicit operator action in
the browser or CLI. Credentials are used only for the active local request; the
redacted proof files record read-only API paths, counts, TLS posture, and
`mutating_calls=0`, not passwords or endpoint values. Do not place credentials
in committed files or baked images; pass approved lab credentials at runtime
through the console, environment variables, mounted secret files, or an
operator-controlled secret store.

For the end-to-end external tester workflow and GitHub reporting expectations,
see [tester-quickstart.md](tester-quickstart.md).

Appliance builds should reuse this container as the inner service and add first
boot setup, TLS certificate handling, local encrypted credential storage, backup,
offline update, and explicit no-telemetry defaults around it.
