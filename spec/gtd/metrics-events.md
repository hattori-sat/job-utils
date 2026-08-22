# GTD Metrics Event Contract

## Storage

Metric events are append-only JSON Lines files in the GTD Markdown Repository:

```text
.jobutils/metrics/events/2026.jsonl
```

Files are partitioned by year for manageable synchronization and inspection.
Reports scan every file intersecting the requested date range, so a report may
compare multiple years without importing data into a separate database.

## Event envelope

Every event has this shape:

```json
{
  "event_id": "8e5b7db5-2ea6-4d4d-a0d6-0fbfe8c3e8fa",
  "event_type": "state_changed",
  "occurred_at": "2026-08-23T10:15:00+09:00",
  "gtd_id": "4f3d0d2f-8b25-4b78-bf67-5e4a0c2f4db0",
  "source": {
    "machine_id": "laptop-a",
    "command": "vim:Gtd"
  },
  "from": {"prefix": "today"},
  "to": {"prefix": "focus"},
  "measure": {
    "active_seconds": null,
    "waiting_seconds": null,
    "scheduled_seconds": null
  },
  "tags": ["delivery", "planning"],
  "impact_level": "medium"
}
```

`machine_id` is a user-defined alias, not a hostname or account identifier.
Optional fields are omitted when they do not apply. Event records must remain
valid JSON on one line.

## Event types

The initial event vocabulary is:

- `captured` and `clarified` for intake and classification;
- `state_changed` for every successful prefix transition;
- `work_started` and `work_stopped` for active-work intervals;
- `waiting_started` and `waiting_stopped` for `wait` intervals;
- `scheduled` for `cal` intent and `schedule_due` for a later Today move;
- `completed` for a move to `done`;
- `published`, `synced`, `error`, and `conflict` for external integration.

## Derived measures

Reports derive these measures from the event stream:

- throughput: completed tasks by period, prefix, tag, impact, and kind;
- active time: sum of work intervals;
- waiting time: sum of waiting intervals, separate from active time;
- scheduled time: time associated with calendar intent, separate from waiting;
- cycle time: first committed state through completion;
- lead time: capture or clarification through completion;
- work-in-progress: concurrent active tasks and Focus occupancy;
- estimate variance: estimate versus recorded active time when both exist.

Counts are supporting context, not a performance score by themselves. Reports
should combine volume, time, impact, task type, and representative outcomes.

