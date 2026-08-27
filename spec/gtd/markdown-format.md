# GTD Markdown Format

## Front matter

Task Markdown begins with standard YAML front matter. Keys and machine-readable
values are English. The `gtd_id` is stable for the life of the task and is the
join key used by Vim, Python, metric events, and external identities.

```yaml
---
gtd_id: 4f3d0d2f-8b25-4b78-bf67-5e4a0c2f4db0
kind: task
prefix: next
status: open
title: Define the delivery checklist
created_at: 2026-08-23T09:00:00+09:00
updated_at: 2026-08-23T09:00:00+09:00
tags: [delivery, planning]
impact_level: medium
estimate_minutes: 60
---
```

The fields above are the task identity, workflow, and measurement metadata.
External synchronization fields are optional and are added only for a
published item. Jira deployment is selected globally by `JIRA_PLATFORM`.
Jira items may use `publish_jira`, `jira_project`,
`jira_issue_type`, `jira_summary_field`, `jira_description_field`,
`jira_assign_to_self`,
`jira_parent_key`, `jira_parent_path`, `jira_progress_comment_field`,
`jira_key`, and `jira_url`. The default Jira field IDs are `summary` and
`description`; front matter values override the corresponding `.env` defaults.
Confluence items may use `publish_confluence`,
`confluence_space_id`, `confluence_space_key`, `confluence_parent_id`,
`confluence_page_id`, `confluence_url`, and `confluence_version`. The sync
engine may also add `sync_hash` after a successful apply. Credentials, cookies,
access tokens, and other secrets never belong in front matter.

Document Markdown also uses `publish_confluence`, `parent_document_id`, and
`confluence_parent_path` to retain the local hierarchy. A document's external
parent is represented by `confluence_parent_id` after apply; the local parent
path remains available for plan generation and rebinding.

The task template also shows the Jira field IDs with safe defaults. Set
`publish_jira: true` and the project/issue type before publishing. A successful
Jira apply fills `jira_key` and `jira_url`; a child task receives its parent's
`jira_parent_key` automatically when created with the subtask command. When
the parent has not been published yet, `jira_parent_path` retains the local
relationship so `sync apply` can create the parent first and then pass its new
Jira key to the child.

Subtasks may add `parent_gtd_id` and `jira_parent_key`. When created with a
parent task, the child Markdown is placed below the parent task's directory.
The `# Subtasks` section is public Markdown and must appear before the final
`# Implementation Note` section. A subtask command accepts a bullet under
that heading and replaces it with a link to the generated child Markdown.
Document Markdown may use the analogous `# Subdocuments` section. A
subdocument command accepts a bullet under that heading, stores the child
below the parent document directory, and can be repeated recursively.

## Task body

Use one level-one heading for each major task field, in this order. Keep three
blank lines after each heading so the Vim workflow has a predictable insertion
area.

```text
# Summary



# Description



# Progress Comment



# Subtasks




# Background



# Objective



# Implementation Note



# Scope

## In



## Out



# Deliverables



# Acceptance Criteria



# Preconditions



# Dependencies



# Risks



# Open Questions



# References



```

`Progress Comment` is ordinary task text. It is not an event log and does not
require date parsing. `Implementation Note` is private working material: it is
kept in Markdown and Git, but its heading and content are excluded from Jira
and Confluence payloads.

## References

Each structured reference has a stable identifier, a local path when known,
and optional external identities. Local Markdown renders the local relative
path. External renderers replace it with a Confluence or Jira URL when the
target is published; they never expose a private Markdown path. An unpublished
target is rendered without a private path.
