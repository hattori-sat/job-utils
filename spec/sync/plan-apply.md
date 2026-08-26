# Sync Plan and Apply Contract

## Source of truth

Markdown in the separate GTD Repository is the canonical local representation.
Jira and Confluence are external projections with stored identifiers and URLs.

## Plan

`sync plan` reads publishable task/document Markdown and the latest observation
from `sync check`, then writes a reviewable JSON plan containing:

- a plan UUID and creation time;
- a hash of the publishable source files;
- the observation ID used to classify external drift, when available;
- one create/update action per external target;
- the target kind, local path, external identity, and sanitized payload;
- import actions for external-only changes and blocking conflict actions for
  two-sided changes.

Plan generation does not call an external write endpoint.

When a Markdown value is empty, the plan builder uses the non-secret defaults
loaded from the local environment: Jira project, issue type, Summary field ID,
Description field ID, and Progress Comment field, plus Confluence space and
default parent page. The standard Jira field IDs default to `summary` and
`description`; setup may confirm and materialize those IDs from Jira's
read-only field catalog. Explicit front matter values take precedence. These
defaults are never written into plans as credentials. Progress Comment remains
a manually configured custom field.

All synchronization JSON and JSONL state belongs to the separate GTD Markdown
Repository under `.jobutils/`: plans are stored in `sync/plans/`, the latest
refresh is `sync/observations/latest.json`, and metric events are stored under
`metrics/events/`. The job-utils repository's `.jobutils/setup/` contains only
utility setup state and logs.

The local `sync status` operation reports plan, base-snapshot, pending-action,
and conflict counts from `.jobutils/` without contacting an external service.

The read-only `sync check` operation refreshes Git remote-tracking metadata
without changing the worktree, fetches current external bodies, and compares them with the local public body
and the last synchronized base. It records an ignored observation and reports
clean, local-only, external-only, converged, conflict, unknown, and per-item
error states without modifying Markdown or any external resource.

## Apply

`sync apply` verifies the source hash and current Git state before executing
actions. A stale plan is rejected and must be regenerated. It also refetches
the external records represented by the observation and stops if their public
body changed after `sync check`. Applying a plan is idempotent when the
external identity is already present. Successful application writes resolved
non-secret routing defaults, external IDs, URLs, versions, and hashes back to
front matter; credentials are never written.

For the Atlassian adapter, `sync apply` commits the generated Markdown and
`.jobutils` synchronization state once after all approved actions complete and
then performs a real Git push to the configured remote. Pending local Markdown
changes are included in that one final commit after the normal credential-path
checks. It stops with the local commit preserved if the push fails. The
`--no-git-sync` option is available for tests and controlled recovery.

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
HTTP adapter for Jira Cloud REST API v2 and Confluence Cloud REST API v2. Jira
descriptions use Jira wiki text; Confluence bodies use storage content.
Bearer authentication is the default for both services, with explicit Basic
authentication available through the corresponding `.env` auth-type setting.

New Jira create actions use the non-secret `JIRA_ASSIGN_TO_SELF` default to
assign the authenticated Jira user. Jira update actions do not change the
existing assignee. A failed current-user lookup stops the create action before
the issue-create request is sent.

Each successful action records `sync_applied` in the repository's append-only
metric event log. An adapter failure records `sync_error` before apply stops.

Classic Vim exposes the same workflow through `:GtdSyncUpdate`, `:GtdSyncCheck`,
`:GtdSyncPlan`, `:GtdSyncApply [plan]`, and `:GtdSyncStatus`. Check and apply
require interactive confirmation; omitting the apply path selects the newest
local plan.

## Check, plan, and conflicts

`sync check` refreshes both sides and records the latest observation. `sync
plan` uses that observation together with the local Markdown and base snapshot.
If only the external side changed, the plan contains an `import` action. If
both sides changed, the plan contains a blocking `conflict` action. Applying a
conflict plan writes standard conflict markers (`<<<<<<< local`, `=======`,
`>>>>>>> external`) to the public body, preserves the local Implementation
Note, records `sync_conflict`, and stops without writing Jira or Confluence.
The user resolves the markers in Vim, runs `sync check` and `sync plan` again,
and applies the reviewed plan.

The launcher and `:GtdSyncUpdate` perform only fast-forward Git updates.
`GtdSyncApply` owns the final commit and push; no separate push command is part
of the normal user workflow.

## Rendering rules

- Task descriptions are rendered to Jira v2 wiki text with headings,
  paragraphs, links, unordered/ordered lists, tables, and fenced code blocks.
- Document bodies are rendered to Confluence storage content with headings,
  paragraphs, links, images, unordered/ordered lists, pipe tables, fenced code
  blocks, and explicit `:::confluence-macro name=...` directives.
- The supported Confluence storage and Jira wiki subset is converted back to
  canonical Markdown during an `import` action. ADF is accepted defensively
  when reading older Jira records.
- Implementation Notes are removed before either payload is created.
- Local relative references are replaced by published external URLs when
  available; private Markdown paths are removed from external text.
- Page parent IDs are written from front matter; page movement is not implied
  by a normal update.
