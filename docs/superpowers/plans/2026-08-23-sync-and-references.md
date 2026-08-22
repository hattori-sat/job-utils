# External Synchronization and References Implementation Plan

## Goal

Implement deterministic Markdown normalization and plan/apply synchronization
for Jira tasks, Confluence documents, and references between them.

## Scope

- Keep Markdown as the canonical local representation.
- Build read-only plans before external writes and require a matching plan for
  apply.
- Map one task Markdown file to one Jira issue, including parent/sub-task
  relationships and Task/Story selection.
- Map document Markdown to a Confluence page with stored parent and page IDs.
- Exclude Implementation Notes from external payloads.
- Convert local reference paths to published external URLs and never expose a
  private Markdown path externally.
- Normalize pulled Jira/Confluence content back to deterministic Markdown and
  expose field or three-way conflicts.

## Files and interfaces

- Create `src/jobutils/markdown/` for YAML, task/document parsing, canonical
  formatting, and Implementation Note extraction.
- Create `src/jobutils/sync/plan.py`, `apply.py`, `state.py`, `jira.py`,
  `confluence.py`, `references.py`, and `merge.py`.
- Create `src/jobutils/cli_sync.py` with `sync plan`, `sync apply`, `sync pull`,
  and `sync rebind` subcommands.
- Create `tests/test_markdown_normalization.py`,
  `tests/test_reference_conversion.py`, `tests/test_sync_plan.py`, and
  `tests/test_merge_conflicts.py`.
- Keep connector credentials in environment/configuration outside the GTD
  repository; store only external IDs and URLs in front matter.

## Verification

- Golden-file tests must produce byte-stable canonical Markdown.
- Plan mode must not write to Jira or Confluence.
- Apply must reject stale plans and must be idempotent on retry.
- Fixtures must cover unpublished references, moved page IDs, parent pages,
  subtasks, Implementation Notes, macros, tables, and conflicts.
- Run focused unit tests, fixture integration tests, and `git diff --check`.
