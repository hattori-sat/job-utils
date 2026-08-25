# Local HTTP Interface

`jobutils serve` starts a small HTTP interface for local integrations. It
binds to `127.0.0.1` by default and does not contact Jira, Confluence, GitHub,
or any other remote service by itself.

```text
jobutils serve --repo REPOSITORY [--host 127.0.0.1] [--port 8765]
```

The supported routes are:

- `GET /health` returns a readiness response.
- `GET /metrics?from=YYYY-MM-DD&to=YYYY-MM-DD` returns the on-demand metrics report.
- `POST /gtd/dispatch` dispatches the GTD index.
- `POST /sync/plan` creates and saves a reviewable synchronization plan.

The service is intended for same-machine integrations. Do not bind it to a
network interface unless access control is provided by the surrounding
environment.
