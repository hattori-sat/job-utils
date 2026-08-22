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
status: next
title: Define the delivery checklist
created_at: 2026-08-23T09:00:00+09:00
updated_at: 2026-08-23T09:00:00+09:00
gtd_file: ../gtd.md
tags: [delivery, planning]
impact_level: medium
impact_area: delivery
estimate_minutes: 60
external:
  jira:
    key: null
    url: null
  confluence:
    page_id: null
    url: null
publish:
  jira: false
  confluence: false
references: []
---
```

The exact external identifiers are populated by synchronization. Credentials,
cookies, access tokens, and other secrets never belong in front matter.

## Task body

Use one level-one heading for each major task field, in this order. Keep three
blank lines after each heading so the Vim workflow has a predictable insertion
area.

```text
# Summary



# Description



# Progress Comment



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

