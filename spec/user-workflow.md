# User Workflow Contract

## Normal operation

The separate GTD Markdown Repository is the user's local source of truth. The
Vim launcher first performs a fast-forward-only Git update. The normal Vim
workflow then has three phases:

1. Use `:Gtd` to move an indexed item between `inbox`, `next`, `today`,
   `focus`, `wait`, `cal`, `someday`, `project`, or `done`.
2. Use `:GtdSyncCheck` to confirm and refresh Git, Jira, and Confluence state.
   It records only an ignored observation and does not pull, commit, or push.
3. Use `:GtdSyncPlan` to review publish/import/conflict actions, then use
   `:GtdSyncApply` to execute them. Apply commits once after all actions and
   pushes that one clean commit.

The user does not manually coordinate a Git push with an Atlassian operation
in the normal workflow.

Jira and Confluence deployment choices are independent. Jira Cloud uses its
Cloud REST adapter, while Jira Data Center uses its REST v2 adapter and
username-based self-assignment; Confluence Data Center remains upload-only
for synchronization checks.

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
- synchronization: `:GtdSyncUpdate`, `:GtdSyncCheck`, `:GtdSyncPlan`,
  `:GtdSyncApply`, `:GtdSyncStatus`, and `:GtdSyncRebind`;
- editing: `:GtdFormat`, `:PasteImage`, and project toolchain commands.

Direct Git fetch and push functions are implementation-level recovery tools,
not normal user commands. `GtdSyncUpdate` is the explicit fast-forward recovery
entry point; the normal synchronization workflow owns both the Markdown
repository and the Jira/Confluence projections.
