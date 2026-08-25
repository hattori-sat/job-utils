# Daily Usage

This page describes the normal workflow after [setup](../setup/README.md).
The GTD Markdown Repository is the working data repository; job-utils provides
the commands and Vim runtime.

## Start work

From any directory, run:

```text
jobutils-vim
```

With no file argument, this opens the configured repository's `gtd.md`. To
open another file explicitly, pass its path:

```text
jobutils-vim /path/to/gtd/documents/guide.md
```

Use `:Gtd` on the indexed line you want to move. The prefix on the line is the
destination, for example `next:`, `today:`, `focus:`, `wait:`, `cal:`, or
`done:`. The move is local and records the transition for metrics. `Focus` may
contain up to three items; it is a concurrent work state, not a required step
in every task's path.

## Create task or document Markdown

`:Gtd` only moves an index item. Use `:GtdTask` when the selected task needs a
detail Markdown file. Use `:GtdDoc` for a document from `docs.md`.

For children, place a bullet under the parent's `# Subtasks` or
`# Subdocuments` heading and run `:GtdSubtask` or `:GtdSubdocument`. The parent
identity is inherited automatically and the child is placed below its parent.

Use `:GtdTaskHelp` and `:GtdDocHelp` when front matter fields or publication
defaults are unclear. `:GtdTags`, `:GtdImpactLevels`, and `:GtdReview` show the
available classifications and current metrics.

## Publish Markdown

Only files whose front matter enables `publish_jira: true` or
`publish_confluence: true` are included in synchronization.

1. Save the Markdown file.
2. Run `:GtdSyncCheck` and confirm the refresh prompt.
3. Run `:GtdSyncPlan` and review the generated plan summary.
4. Run `:GtdSyncApply` and confirm the prompt.

Apply updates Jira or Confluence, writes returned IDs and URLs to front
matter, commits the Markdown and synchronization state, and pushes the commit
to the configured Git remote. Implementation Notes remain local.

## Synchronize before editing

Run `:GtdSyncCheck` before planning work on another computer or after an
external Jira/Confluence edit. Confirm the refresh prompt. It updates Git's
remote-tracking information, fetches current Jira and Confluence records, and
writes an ignored observation without committing or pushing.

Then run:

```text
:GtdSyncPlan
:GtdSyncApply
```

An external-only change becomes an import action. If both Markdown and the
external record changed, apply writes conflict markers into the Markdown file
and stops without an external write. Resolve the markers in Vim, save, run
`:GtdSyncCheck` and `:GtdSyncPlan` again, then apply the reviewed plan.

There is no separate GitHub, Jira, or Confluence pull command in the normal
workflow. `:GtdSyncApply` commits once after all approved actions and pushes
that commit.

## Review and reports

`:GtdReview` shows the current review summary. For a period report, use the
Python wrapper:

```text
jobutils metrics report --repo /path/to/gtd --from 2026-01-01 --to 2026-12-31 --format html,csv,svg
```

The report separates active, waiting, and scheduled time and groups results by
tag, impact, prefix, and task kind. Reports are generated under the GTD
repository's ignored output directory.

## Other Vim helpers

- `:GtdFormat` formats a saved Markdown file.
- `:PasteImage diagram` saves a clipboard PNG under `assets/` and inserts a
  Markdown link.
- `:JobutilsProjectRoot` and `:JobutilsCMake` help navigate C/C++ projects.
- `:JobutilsCMakeBuild`, `:JobutilsCMakeTest`, `:JobutilsMake`, and
  `:JobutilsQuickfix` support the local toolchain.
