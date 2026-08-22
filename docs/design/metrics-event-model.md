# Metrics Event Model

## Timeline model

An item's history is a sequence of immutable events joined by `gtd_id`. The
current front matter is a materialized view of the latest successful state;
the JSONL stream is the historical source for time and flow analysis.

```text
captured → clarified → next → today → focus → wait → today → focus → cal
                                                                  ↓
                                                                 today → done
```

The same item may enter Focus more than once and may alternate between active,
waiting, and scheduled periods. Reports must not assume one uninterrupted work
interval.

## Measurement rules

- A state transition records `from.prefix`, `to.prefix`, and its timestamp.
- Work intervals are explicit so a user can stop active-time accounting without
  changing the task's GTD placement.
- Entering `wait` closes an active interval and opens a waiting interval.
- Leaving `wait` closes waiting time; it does not retroactively count as work.
- Entering `cal` records scheduled intent and closes active work if necessary.
- `cal → today` records that scheduled work became actionable.
- Completion closes any open interval and records the completion timestamp.

If an older event file is incomplete, the report marks the derived interval as
partial instead of inventing a duration. Duplicate `event_id` values are
ignored during aggregation after the first valid occurrence.

## Reporting dimensions

The event contract supports annual reviews and shorter explorations by:

- calendar period and arbitrary date range;
- task kind, tag, impact level, and impact area;
- GTD state and transition path;
- active, waiting, scheduled, cycle, and lead time;
- completed outcomes and linked documents where available.

HTML, CSV, and SVG are generated on demand from these events. The source event
files remain the portable, Git-friendly record.
