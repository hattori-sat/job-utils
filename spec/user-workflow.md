# User Workflow Contract

## Normal operation

The separate GTD Markdown Repository is the user's local source of truth. The
normal Vim workflow has three phases:

1. Use `:Gtd` to move an indexed item between `inbox`, `next`, `today`,
   `focus`, `wait`, `cal`, `someday`, `project`, or `done`.
2. Use `:GtdSyncPlan` to review proposed Jira and Confluence changes, then use
   `:GtdSyncApply` to publish them. Apply commits and pushes the Markdown and
   synchronization state as one operation.
3. Use `:GtdSyncPull` when beginning work on another computer or when external
   changes may exist. It fast-forwards the Markdown repository, imports
   external Jira/Confluence changes, commits any imported changes, and pushes
   the resulting repository state.

The user does not manually coordinate a Git push with an Atlassian operation
in the normal workflow.

## Metrics

Every successful `:Gtd` transition records a state event. Active time is
derived from `today` and `focus`, waiting time from `wait`, and scheduled time
from `cal`. `:GtdReview` and the report commands summarize these events. The
low-level Python event API may retain explicit interval support for migration
and diagnostics, but explicit start/stop commands are not part of the normal
Vim workflow.

## Command surface

The normal Vim entry points are:

- GTD: `:Gtd`, `:GtdTask`, `:GtdSubtask`, `:GtdDoc`, `:GtdSubdocument`;
- review: `:GtdReview`, `:GtdTags`, `:GtdImpactLevels`, and help commands;
- synchronization: `:GtdSyncPlan`, `:GtdSyncApply`, `:GtdSyncPull`,
  `:GtdSyncStatus`, `:GtdSyncCheck`, and `:GtdSyncRebind`;
- editing: `:GtdFormat`, `:PasteImage`, and project toolchain commands.

Direct Git push and pull commands are implementation-level recovery tools, not
normal user commands. The normal synchronization entry point owns both the
Markdown repository and the Jira/Confluence projections.
