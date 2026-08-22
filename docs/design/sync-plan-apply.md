# Sync Plan and Apply Design

The synchronization path is intentionally split into four boundaries:

```text
Markdown parser → canonical public body → plan → adapter apply
       ↑                                  ↓
       └──── external IDs and URLs ←──────┘
```

The parser owns YAML and the local task/document distinction. The public-body
step removes the final `# Implementation Note` section and resolves references
against the local publication map. The plan is a JSON artifact that can be
reviewed and checked for staleness. The adapter owns HTTP details and external
response shapes.

## Current operational modes

- `sync plan` is read-only with respect to Jira and Confluence.
- `sync apply --adapter memory` is deterministic for tests and local exercises.
- `sync apply --adapter atlassian` reads credentials from environment variables
  and calls the current Atlassian Cloud REST endpoints.

The external adapter is deliberately not invoked by Vim's `:Gtd` command.
GTD movement remains a local operation; synchronization is an explicit review
and apply workflow.
