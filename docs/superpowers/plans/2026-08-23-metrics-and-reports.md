# Metrics and Reports Implementation Plan

## Goal

Record portable JSONL events from GTD operations and generate cross-year,
date-range reports for work, waiting, scheduling, throughput, impact, and
outcomes.

## Scope

- Append one valid JSON object per event to a year-partitioned event file.
- Keep event IDs and task IDs stable across machines and Git merges.
- Derive active, waiting, scheduled, cycle, lead, WIP, throughput, and estimate
  variance measures without SQLite.
- Provide readable Vim commands for the tag and impact catalogs and GTD review.
- Generate HTML, CSV, and SVG on demand below `.jobutils/output/<date>/<period>/`.

## Files and interfaces

- Create `src/jobutils/metrics/events.py`, `reader.py`, `aggregate.py`, and
  `reports.py`.
- Create `src/jobutils/cli_metrics.py` with `metrics review`, `metrics report`,
  and `metrics validate`.
- Create `src/jobutils/metrics/catalog.py` with the default tags and impact
  levels.
- Extend `vim/autoload/jobutils/gtd.vim` with `:GtdTags`, `:GtdImpactLevels`,
  `:GtdMetricsHelp`, and `:GtdReview`.
- Create `tests/test_metrics_events.py`, `tests/test_metrics_aggregate.py`,
  and `tests/test_reports.py`.

## Verification

- Test event append, duplicate suppression, malformed-line reporting, and
  multi-year range queries.
- Test the transition sequence `next → today → focus → wait → today → focus →
  cal → today → done` and confirm separate durations.
- Test report filters and generated HTML/CSV/SVG against golden fixtures.
- Confirm generated output is ignored and no credentials are written.
