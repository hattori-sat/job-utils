# GTD State Graph

The GTD workflow is a directed graph with flexible user-driven transitions.
The sections in `gtd.md` provide the visible placement; the event log provides
the history needed to understand how an item reached its current placement.

```mermaid
flowchart LR
    Inbox --> next
    next --> today
    next --> focus
    today --> focus
    focus --> next
    focus --> today
    focus --> wait
    focus --> cal
    wait --> today
    cal --> today
    today --> done
    focus --> done
    next --> someday
    someday --> next
    project --> next
```

The diagram shows common transitions, not an exhaustive allow-list. Any known
non-Inbox destination is valid from any known source. Inbox is shown only as
an intake origin and is never a dispatch destination.

## Time interpretation

- Active work time is accumulated while the item is in a user-selected active
  state such as Today or Focus, according to recorded work events.
- Waiting time begins when the item enters `wait` and ends when it leaves
  `wait`.
- Scheduled time is recorded when the item enters `cal`; it is neither active
  work nor waiting time.
- A later `cal → today` transition records that the scheduled item became due
  and can begin active work.

The event stream, rather than the current section alone, is the source for
cycle-time and flow analysis.
