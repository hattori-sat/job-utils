# job-utils Requirements

## Purpose

Provide a portable utility layer for a Vim-centered GTD workflow whose actual
Markdown data is maintained in a separate Git repository.

## Required capabilities

- Dispatch GTD items from `gtd.md` using prefixes.
- Keep task and document Markdown in the separate GTD Repository.
- Create and maintain task detail Markdown with YAML front matter.
- Represent task relationships, document references, Jira issues, and
  Confluence pages with stable identifiers.
- Publish selected task content to Jira and selected document content to
  Confluence through explicit, reviewable synchronization operations.
- Record task-state and work-time events in Git-friendly JSONL.
- Produce period-based Markdown, CSV, SVG, and local HTML reports.
- Provide Vim commands and Python CLI commands over the same domain logic.
- Provide setup guidance for Windows, macOS, and Ubuntu without making Docker
  mandatory.
- Keep AI-agent guidance and skill references available without automatic skill
  installation.

## Important invariants

- The job-utils Repository and GTD Repository are separate.
- `gtd.md` is the GTD task index; `docs.md` is the document index.
- Inbox is an intake area and is not a dispatch destination.
- Known non-Inbox prefixes may move freely between sections.
- `focus` may contain at most three items. A fourth item causes an atomic
  dispatch failure.
- Calendar time is scheduled time, not waiting time.
- Implementation Notes are retained in Markdown but are not published to Jira
  or Confluence.
- Authentication material, tokens, cookies, and personal secrets are never
  committed.
- Generated reports are written under Git-ignored output directories.
- SQLite and Docker are not required components.

## Completion criteria for the foundation

- The domain vocabulary is stable enough to write focused feature
  specifications.
- The GTD dispatch and state invariants are written in `spec/gtd/`.
- Agent guidance is available in the repository-native instruction locations.
- Research notes remain separate from normative specifications.
