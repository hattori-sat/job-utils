"""Generate human-readable metric reports from the event stream."""

import csv
import html
import io
import json
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from .aggregate import aggregate
from .reader import read_events


def day_start(value: str) -> datetime:
    """Return the UTC beginning of an ISO calendar date."""

    return datetime.combine(
        datetime.fromisoformat(value).date(), time.min, tzinfo=timezone.utc
    )


def day_end(value: str) -> datetime:
    """Return the UTC end of an ISO calendar date."""

    return datetime.combine(
        datetime.fromisoformat(value).date(), time.max, tzinfo=timezone.utc
    )


def build_report(repo_root: Path, start: str, end: str) -> Dict:
    """Read and aggregate events for an inclusive date range."""

    events, errors = read_events(repo_root)
    report = aggregate(events, day_start(start), day_end(end))
    report["read_errors"] = errors
    return report


def csv_text(report: Dict) -> str:
    """Render task metrics as CSV text."""

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "gtd_id",
            "kind",
            "captured_at",
            "first_state_at",
            "active_seconds",
            "waiting_seconds",
            "scheduled_seconds",
            "cycle_seconds",
            "lead_seconds",
            "estimate_minutes",
            "estimate_variance_seconds",
            "transitions",
            "final_prefix",
            "completed_at",
            "tags",
            "impact_level",
        ]
    )
    for task in report["tasks"]:
        writer.writerow(
            [
                task["gtd_id"],
                task["kind"] or "",
                task["captured_at"] or "",
                task["first_state_at"] or "",
                task["active_seconds"],
                task["waiting_seconds"],
                task["scheduled_seconds"],
                task["cycle_seconds"],
                task["lead_seconds"],
                task["estimate_minutes"] if task["estimate_minutes"] is not None else "",
                task["estimate_variance_seconds"]
                if task["estimate_variance_seconds"] is not None
                else "",
                task["transitions"],
                task["final_prefix"],
                task["completed_at"] or "",
                ",".join(task["tags"]),
                task["impact_level"] or "",
            ]
        )
    return output.getvalue()


def json_text(report: Dict) -> str:
    """Render the complete report for later analysis or dashboard tooling."""

    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def html_text(report: Dict) -> str:
    """Render a compact HTML summary and task table."""

    summary = [
        ("Tasks", report["task_count"]),
        ("Completed", report["completed_count"]),
        ("Active seconds", report["active_seconds"]),
        ("Waiting seconds", report["waiting_seconds"]),
        ("Scheduled seconds", report["scheduled_seconds"]),
        ("Lead seconds", report["lead_seconds"]),
        ("Cycle seconds", report["cycle_seconds"]),
    ]
    cards = "".join(
        "<section><h2>{}</h2><p>{}</p></section>".format(html.escape(str(label)), value)
        for label, value in summary
    )
    rows = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            html.escape(task["gtd_id"]),
            task["active_seconds"],
            task["waiting_seconds"],
            task["scheduled_seconds"],
            html.escape(task["final_prefix"] or ""),
            "yes" if task["completed_in_period"] else "no",
            html.escape(", ".join(task["tags"])),
        )
        for task in report["tasks"]
    )
    tag_rows = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            html.escape(key),
            values["task_count"],
            values["completed_count"],
            values["active_seconds"],
        )
        for key, values in sorted(report["by_tag"].items())
    )
    errors = "".join(
        "<li>{}</li>".format(html.escape(error)) for error in report["read_errors"]
    )
    daily_json = json.dumps(report["daily_throughput"], ensure_ascii=False).replace(
        "<", "\\u003c"
    )
    return """<!doctype html>
<html lang="en"><meta charset="utf-8"><title>Job Utils Metrics</title>
<style>body{{font:16px system-ui;margin:2rem}}main{{display:flex;gap:1rem;flex-wrap:wrap}}
section{{border:1px solid #ccc;padding:1rem;min-width:9rem}}table{{border-collapse:collapse;margin-top:2rem}}
td,th{{border:1px solid #ccc;padding:.4rem}}#throughput-chart{{display:grid;gap:.35rem;max-width:48rem}}
.throughput-bar{{background:#4c78a8;color:white;padding:.25rem .5rem;min-width:2rem}}</style>
<h1>Task metrics</h1><p>{start} to {end}</p><main>{cards}</main>
<h2>Throughput</h2><label>From <input id="throughput-start" type="date" value="{start_date}"></label>
<label>To <input id="throughput-end" type="date" value="{end_date}"></label>
<output id="throughput-total"></output><div id="throughput-chart"></div>
<h2>By tag</h2><table><thead><tr><th>Tag</th><th>Tasks</th><th>Completed</th><th>Active seconds</th></tr></thead><tbody>{tag_rows}</tbody></table>
<h2>Tasks</h2><table><thead><tr><th>Task</th><th>Active</th><th>Waiting</th><th>Scheduled</th><th>State</th><th>Done</th><th>Tags</th></tr></thead>
<tbody>{rows}</tbody></table>{error_block}
<script>const throughput={daily_json};
function renderThroughput() {{
  const start=document.getElementById('throughput-start').value;
  const end=document.getElementById('throughput-end').value;
  const rows=throughput.filter(row => row.date >= start && row.date <= end);
  const max=Math.max(1, ...rows.map(row => row.completed_count));
  document.getElementById('throughput-total').textContent=' Completed: '+rows.reduce((sum,row) => sum+row.completed_count, 0);
  document.getElementById('throughput-chart').innerHTML=rows.map(row => '<div class="throughput-bar" style="width:'+Math.round(row.completed_count/max*100)+'%">'+row.date+': '+row.completed_count+'</div>').join('');
}}
document.getElementById('throughput-start').addEventListener('change', renderThroughput);
document.getElementById('throughput-end').addEventListener('change', renderThroughput);
renderThroughput();</script></html>""".format(
        start=html.escape(report["period"]["start"]),
        end=html.escape(report["period"]["end"]),
        start_date=html.escape(report["period"]["start"][:10]),
        end_date=html.escape(report["period"]["end"][:10]),
        cards=cards,
        tag_rows=tag_rows,
        rows=rows,
        daily_json=daily_json,
        error_block="<h2>Read errors</h2><ul>{}</ul>".format(errors) if errors else "",
    )


def svg_text(report: Dict) -> str:
    """Render an SVG bar chart for active, waiting, and scheduled time."""

    values = [
        ("active", report["active_seconds"]),
        ("waiting", report["waiting_seconds"]),
        ("scheduled", report["scheduled_seconds"]),
    ]
    maximum = max([value for _, value in values] + [1])
    bars = []
    for index, (label, value) in enumerate(values):
        width = int(500 * value / maximum)
        y = 30 + index * 42
        bars.append(
            '<text x="0" y="{}">{}</text><rect x="100" y="{}" width="{}" height="24" fill="#4c78a8"/><text x="{}" y="{}">{}</text>'.format(
                y + 18, html.escape(label), y, width, 110 + width, y + 18, value
            )
        )
    return '<svg xmlns="http://www.w3.org/2000/svg" width="700" height="170" role="img"><title>Task time</title>{}</svg>'.format(
        "".join(bars)
    )


def write_reports(
    repo_root: Path,
    start: str,
    end: str,
    formats: Sequence[str],
    output_dir: Optional[Path] = None,
) -> List[Path]:
    """Write requested report formats to a dated output directory."""

    report = build_report(repo_root, start, end)
    period = "{}_to_{}".format(start, end)
    target = output_dir or (
        Path(repo_root)
        / ".jobutils"
        / "output"
        / datetime.now().date().isoformat()
        / period
    )
    target.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for format_name in formats:
        path = target / ("metrics." + format_name)
        if format_name == "html":
            path.write_text(html_text(report), encoding="utf-8")
        elif format_name == "csv":
            path.write_text(csv_text(report), encoding="utf-8")
        elif format_name == "svg":
            path.write_text(svg_text(report), encoding="utf-8")
        elif format_name == "json":
            path.write_text(json_text(report), encoding="utf-8")
        else:
            raise ValueError("unsupported report format: {}".format(format_name))
        written.append(path)
    return written
