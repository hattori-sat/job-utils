# Synchronization Drift Check Contract

## Purpose

`sync check` is a read-only refresh operation. It refreshes Git remote-tracking
metadata and reads the public Markdown body, the last synchronized base
snapshot, and the current external body, then reports their relationship. It
writes only the latest ignored observation under
`.jobutils/sync/observations/latest.json`; it does not write plans, front
matter, base snapshots, Markdown, Jira, or Confluence, and it never commits or
pushes.

## States

| State | Meaning |
| --- | --- |
| `clean` | Local and external bodies both equal the last base. |
| `external_changed` | Local equals the base, but the external body differs. |
| `local_changed` | External equals the base, but local Markdown differs. |
| `conflict` | Both sides differ from the base and from each other. |
| `converged` | Both sides changed from the base but now contain the same body. |
| `unknown` | No base snapshot exists, so the change origin cannot be determined. |
| `error` | The item could not be parsed or fetched; the error is isolated to that item. |

Items without a publish flag or external ID are not checked. Implementation
Notes are excluded because comparisons use the parsed public body.

## Interfaces

```text
jobutils sync check --repo REPO --adapter memory|atlassian
jobutils sync check --repo REPO --adapter memory|atlassian --no-git-fetch
:GtdSyncCheck
:gtdsynccheck
```

The CLI prints one JSON object:

```json
{
  "checked": 1,
  "error_count": 0,
  "observation_id": "...",
  "git": {
    "performed": true,
    "remote": "origin",
    "branch": "main",
    "remote_revision": "..."
  },
  "items": [
    {
      "path": "documents/guide.md",
      "kind": "confluence",
      "external_id": "PAGE-42",
      "external_url": "https://example.invalid/wiki/pages/PAGE-42",
      "state": "clean"
    }
  ]
}
```

The process exits with status 1 when one or more items are in `error`; drift
states themselves are reported successfully. The latest observation is the
input to `sync plan`. An external-only change becomes an `import` action, a
two-sided change becomes a `conflict` action, and a local-only change remains
an external update. Use `--no-git-fetch` only when the Git remote is
intentionally unavailable.
