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

Health endpoint:

```text
http://localhost:8080/healthz
```

The container writes the generated console site under `/data/console-site`.
With the included Compose file, that maps to `.\data` on the host.

The image does not contact vCenter, Prism Central, Nutanix Move, AHV, or NC2 by
itself. Live endpoint collection still requires explicit approved local commands
and read-only proof. Do not place credentials in committed files or baked images;
pass approved lab credentials at runtime through environment variables, mounted
secret files, or an operator-controlled secret store.

Appliance builds should reuse this container as the inner service and add first
boot setup, TLS certificate handling, local encrypted credential storage, backup,
offline update, and explicit no-telemetry defaults around it.
