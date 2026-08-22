import csv
import html
import io
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from .aggregate import aggregate
from .reader import read_events


def day_start(value: str) -> datetime:
    return datetime.combine(datetime.fromisoformat(value).date(), time.min, tzinfo=timezone.utc)


def day_end(value: str) -> datetime:
    return datetime.combine(datetime.fromisoformat(value).date(), time.max, tzinfo=timezone.utc)


def build_report(repo_root: Path, start: str, end: str) -> Dict:
    events, errors = read_events(repo_root)
    report = aggregate(events, day_start(start), day_end(end))
    report["read_errors"] = errors
    return report


def csv_text(report: Dict) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([
        "gtd_id", "active_seconds", "waiting_seconds", "scheduled_seconds",
        "cycle_seconds", "transitions", "final_prefix", "completed_at", "tags",
        "impact_level",
    ])
    for task in report["tasks"]:
        writer.writerow([
            task["gtd_id"], task["active_seconds"], task["waiting_seconds"],
            task["scheduled_seconds"], task["cycle_seconds"], task["transitions"],
            task["final_prefix"], task["completed_at"] or "", ",".join(task["tags"]),
            task["impact_level"] or "",
        ])
    return output.getvalue()


def html_text(report: Dict) -> str:
    summary = [
        ("Tasks", report["task_count"]),
        ("Completed", report["completed_count"]),
        ("Active seconds", report["active_seconds"]),
        ("Waiting seconds", report["waiting_seconds"]),
        ("Scheduled seconds", report["scheduled_seconds"]),
    ]
    cards = "".join(
        "<section><h2>{}</h2><p>{}</p></section>".format(html.escape(str(label)), value)
        for label, value in summary
    )
    rows = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            html.escape(task["gtd_id"]), task["active_seconds"], task["waiting_seconds"],
            task["scheduled_seconds"], html.escape(task["final_prefix"] or ""),
            "yes" if task["completed_at"] else "no",
        )
        for task in report["tasks"]
    )
    errors = "".join("<li>{}</li>".format(html.escape(error)) for error in report["read_errors"])
    return """<!doctype html>
<html lang="en"><meta charset="utf-8"><title>Job Utils Metrics</title>
<style>body{{font:16px system-ui;margin:2rem}}main{{display:flex;gap:1rem;flex-wrap:wrap}}
section{{border:1px solid #ccc;padding:1rem;min-width:9rem}}table{{border-collapse:collapse;margin-top:2rem}}
td,th{{border:1px solid #ccc;padding:.4rem}}</style>
<h1>Task metrics</h1><p>{start} to {end}</p><main>{cards}</main>
<table><thead><tr><th>Task</th><th>Active</th><th>Waiting</th><th>Scheduled</th><th>State</th><th>Done</th></tr></thead>
<tbody>{rows}</tbody></table>{error_block}</html>""".format(
        start=html.escape(report["period"]["start"]),
        end=html.escape(report["period"]["end"]),
        cards=cards,
        rows=rows,
        error_block="<h2>Read errors</h2><ul>{}</ul>".format(errors) if errors else "",
    )


def svg_text(report: Dict) -> str:
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
    return '<svg xmlns="http://www.w3.org/2000/svg" width="700" height="170" role="img"><title>Task time</title>{}</svg>'.format("".join(bars))


def write_reports(repo_root: Path, start: str, end: str, formats: Sequence[str], output_dir: Optional[Path] = None) -> List[Path]:
    report = build_report(repo_root, start, end)
    period = "{}_to_{}".format(start, end)
    target = output_dir or (Path(repo_root) / ".jobutils" / "output" / datetime.now().date().isoformat() / period)
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
        else:
            raise ValueError("unsupported report format: {}".format(format_name))
        written.append(path)
    return written
