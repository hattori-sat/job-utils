# GTD Dispatch Contract

## Command

The Vim `:Gtd` command remains the user-facing dispatcher. It reads the
current item's selected prefix, moves the item to the matching section in
`gtd.md`, and synchronizes the linked task Markdown when one exists. There is
no separate Focus command.

The Python implementation is the shared domain operation. Vim is responsible
for collecting the current buffer context and presenting the result or error.

## Destination rules

1. Every known prefix, including `inbox`, is a valid destination.
2. An `inbox` transition returns the item to the Inbox section and is recorded
   as a normal state transition.
3. An unknown prefix is not silently converted to another prefix. The command
   must reject it or leave the item unchanged according to the parser result.
4. Existing section names and whole-file scanning behavior remain supported;
   adding `focus` must not break the other known prefixes.

## Transactional algorithm

Dispatch is a preflight-and-commit operation:

1. Parse the current item, its source section, and its requested destination.
2. Validate the destination and resolve or create the stable task identity.
3. Compute the resulting section counts from the proposed change.
4. Reject the operation before writing when the resulting Focus count would be
   greater than three.
5. When validation succeeds, update `gtd.md`, linked front matter, and the
   metric event as one logical operation.
6. Refresh the Vim buffer and report success.

If any validation in steps 1–4 fails, no source-line deletion, destination
append, linked-file update, or metric event is written. The Focus-limit error
shown to the user is exactly:

```text
GTD: dispatch failed
```

The detailed reason may be written to `.jobutils` and shown by a status command,
but the Vim failure line remains stable for scripts and muscle memory.

## Identity and linked Markdown

Dispatch does not create task Markdown. A known item without a detail link is
moved as an unlinked item. The explicit Vim `:GtdTask` command or Python
`gtd task` operation creates one task Markdown file below `gtd_tasks/`, assigns
a UUID, and replaces only the selected index line with the generated link.
Existing links and UUIDs are reused. An unlinked `done` item is invalid and is
not auto-created; this preserves the safety rule that completed work must have
a detail record before it is closed.

## Observability

Every successful prefix change on a linked task produces a metric event
containing the previous and new prefixes. Creating a task through `:GtdTask` or
`gtd task` produces its capture event. Moving an unlinked item does not create a
task identity or metric event. A failed dispatch produces an error event
without changing the task state. `wait` starts waiting-time accounting; `cal`
records scheduled intent and does not start waiting-time accounting.
