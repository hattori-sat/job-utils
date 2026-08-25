# External Identity Rebind Contract

## Purpose

Rebind changes the local Markdown record for an already-known external item.
It does not call Jira or Confluence, move a page, or overwrite public body
content. The next `sync plan` treats the changed front matter as the current
local identity.

## Command

```text
jobutils sync rebind --repo REPO --path MANAGED.md \
  --kind jira|confluence --external-id ID [--url URL] [--parent-id ID]
```

`MANAGED.md` must be a regular file below `gtd_tasks/` or `documents/` and
must contain YAML front matter. `--external-id` accepts one non-empty token
made from letters, digits, `.`, `_`, `:`, or `-`. The optional URL must be an
absolute HTTP or HTTPS URL. The optional parent ID uses
`jira_parent_key` for Jira and `confluence_parent_id` for Confluence.

The command updates only the identity fields for the selected kind:

| Kind | Required field | Optional fields |
| --- | --- | --- |
| Jira | `jira_key` | `jira_url`, `jira_parent_key` |
| Confluence | `confluence_page_id` | `confluence_url`, `confluence_parent_id` |

The file is replaced atomically. Invalid paths, identifiers, URLs, or front
matter fail before the original file is changed. Credentials and tokens are
never accepted as command arguments or stored by this operation.
