# Sync Plan and Apply Contract

## Source of truth

Markdown in the separate GTD Repository is the canonical local representation.
Jira and Confluence are external projections with stored identifiers and URLs.

## Plan

`sync plan` reads publishable task/document Markdown and writes a reviewable
JSON plan containing:

- a plan UUID and creation time;
- a hash of the publishable source files;
- one create/update action per external target;
- the target kind, local path, external identity, and sanitized payload.

Plan generation does not call an external write endpoint.

When a Markdown value is empty, the plan builder uses the non-secret defaults
loaded from the local environment: Jira project, issue type, and progress
comment field, plus Confluence space and default parent page. Explicit front
matter values take precedence. These defaults are never written into plans as
credentials.

The local `sync status` operation reports plan, base-snapshot, pending-action,
and conflict counts from `.jobutils/` without contacting an external service.

## Apply

`sync apply` verifies the source hash before executing actions. A stale plan is
rejected and must be regenerated. Applying a plan is idempotent when the
external identity is already present. Successful application writes only
external IDs, URLs, versions, and hashes back to front matter; credentials are
never written.

Confluence actions include a local `parent_path` when a child document has a
parent Markdown file. Apply orders parent actions before children and passes a
newly-created parent's page ID to the child request. The resolved
`confluence_parent_id` is written back to the child front matter.

Jira subtask actions use the same dependency model. A child task may carry
`jira_parent_path`; apply orders the Jira parent first and passes its created or
stored issue key to the child request. The resolved `jira_parent_key` is
written back to the child front matter. An unresolved required parent stops
the apply before the child request is sent.

The adapter boundary supports a deterministic memory adapter for tests and an
HTTP adapter for Jira Cloud REST API v3 and Confluence Cloud REST API v2.

Classic Vim exposes the same workflow through `:GtdSyncPlan`,
`:GtdSyncApply [plan]`, `:GtdSyncPull`, and `:GtdSyncStatus`. Apply and pull
require interactive confirmation; omitting the apply path selects the newest
local plan.

## Pull and conflicts

`sync pull` reads external content and compares it with the last synchronized
public Markdown body. If only one side changed, that side is accepted. If both
local and external content changed, the public body receives standard conflict
markers (`<<<<<<< local`, `=======`, `>>>>>>> external`) and the command
reports a conflict without silently choosing a side. The local Implementation
Note is preserved below the merged public body.

## Rendering rules

- Task descriptions are rendered to Jira ADF with headings, paragraphs, links,
  unordered/ordered lists, tables, and fenced code blocks.
- Document bodies are rendered to Confluence storage content with headings,
  paragraphs, links, images, unordered/ordered lists, pipe tables, fenced code
  blocks, and explicit `:::confluence-macro name=...` directives.
- The supported Confluence storage and Jira ADF subset is converted back to
  canonical Markdown during pull.
- Implementation Notes are removed before either payload is created.
- Local relative references are replaced by published external URLs when
  available; private Markdown paths are removed from external text.
- Page parent IDs are written from front matter; page movement is not implied
  by a normal update.
