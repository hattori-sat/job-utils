# GTD State Model

## Purpose

The GTD Markdown Repository uses prefixes to express the current placement of
an item in `gtd.md`. A prefix is a workflow state and may be changed by the
Vim `:Gtd` command.

## Prefix vocabulary

| Prefix | Display label | Meaning |
| --- | --- | --- |
| `next` | Next Actions | An actionable item that is ready to be selected. |
| `today` | Today | An item that should be worked on today. |
| `focus` | Focus | An item currently receiving active attention. |
| `wait` | Waiting | Work paused while an external condition or person is awaited. |
| `cal` | Calendar | Work associated with a scheduled date or time. |
| `someday` | Someday | A possible item with no current commitment. |
| `project` | Projects | A multi-step outcome or project container. |
| `done` | Done | An item whose work is complete. |

Inbox is an intake location, not a dispatch prefix. Display labels may be
localized in Vim and reports; front matter and event records use the English
prefix values above.

## State properties

- `prefix` is the authoritative current placement.
- `status` may be retained as a compatibility mirror of `prefix`; it must not
  contradict `prefix` after a successful dispatch.
- A task may have any number of non-Inbox transitions. The model is a graph,
  not a prescribed sequence.
- Focus is a concurrency limit, not a workflow lock. Up to three items may be
  in Focus at once.
- A scheduled Calendar item may later be moved to Today when its date arrives.
  That move records the schedule history; it does not turn the prior period
  into Waiting.

## Allowed transition rule

Any known prefix may move to any other known non-Inbox prefix when the user
dispatches it. This includes, for example:

```text
next → today → focus → wait → today → focus → cal → today → done
focus → next
focus → wait
focus → cal
```

The implementation records the transition and its timestamps. It does not
reject a transition merely because it is not in the examples above.
