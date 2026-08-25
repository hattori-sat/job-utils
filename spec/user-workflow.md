# User Workflow Contract

## Normal operation

The separate GTD Markdown Repository is the user's local source of truth. The
normal Vim workflow has three phases:

1. Use `:Gtd` to move an indexed item between `inbox`, `next`, `today`,
   `focus`, `wait`, `cal`, `someday`, `project`, or `done`.
2. Use `:GtdSyncCheck` to confirm and refresh Git, Jira, and Confluence state.
   It records only an ignored observation and does not commit or push.
3. Use `:GtdSyncPlan` to review publish/import/conflict actions, then use
   `:GtdSyncApply` to execute them. Apply commits once after all actions and
   pushes that one clean commit.

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
- synchronization: `:GtdSyncCheck`, `:GtdSyncPlan`, `:GtdSyncApply`,
  `:GtdSyncStatus`, and `:GtdSyncRebind`;
- editing: `:GtdFormat`, `:PasteImage`, and project toolchain commands.

Direct Git fetch, push, and pull functions are implementation-level recovery
tools, not normal user commands. The normal synchronization workflow owns both
the Markdown repository and the Jira/Confluence projections.
