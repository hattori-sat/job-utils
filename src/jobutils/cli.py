import argparse
from datetime import date
import json
import sys
from pathlib import Path
from typing import List, Optional

from .gtd import DispatchError, create_task, dispatch
from .metrics.catalog import DEFAULT_TAGS, IMPACT_LEVELS
from .metrics.reader import read_events
from .metrics.reports import write_reports


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jobutils")
    subparsers = parser.add_subparsers(dest="domain")
    gtd = subparsers.add_parser("gtd")
    gtd_subparsers = gtd.add_subparsers(dest="operation")
    dispatch_parser = gtd_subparsers.add_parser("dispatch")
    dispatch_parser.add_argument("--repo", default=".")
    dispatch_parser.add_argument("--gtd-file", default=None)
    dispatch_parser.add_argument("--machine-id", default=None)
    task_parser = gtd_subparsers.add_parser("task")
    task_parser.add_argument("--repo", default=".")
    task_parser.add_argument("--gtd-file", default=None)
    task_parser.add_argument("--line", type=int, required=True)
    metrics = subparsers.add_parser("metrics")
    metrics_subparsers = metrics.add_subparsers(dest="operation")
    report_parser = metrics_subparsers.add_parser("report")
    report_parser.add_argument("--repo", default=".")
    report_parser.add_argument("--from", dest="start", required=True)
    report_parser.add_argument("--to", dest="end", required=True)
    report_parser.add_argument("--format", default="html,csv,svg")
    report_parser.add_argument("--output-dir", default=None)
    metrics_subparsers.add_parser("validate").add_argument("--repo", default=".")
    catalog_parser = metrics_subparsers.add_parser("catalog")
    catalog_parser.add_argument("--repo", default=".")
    review_parser = metrics_subparsers.add_parser("review")
    review_parser.add_argument("--repo", default=".")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    if args.domain == "metrics" and args.operation == "report":
        formats = [value.strip() for value in args.format.split(",") if value.strip()]
        output_dir = Path(args.output_dir) if args.output_dir else None
        paths = write_reports(Path(args.repo), args.start, args.end, formats, output_dir)
        for path in paths:
            print(path)
        return 0
    if args.domain == "metrics" and args.operation == "validate":
        _, errors = read_events(Path(args.repo))
        for error in errors:
            print(error, file=sys.stderr)
        return 1 if errors else 0
    if args.domain == "metrics" and args.operation == "catalog":
        print("Tags:")
        for tag in DEFAULT_TAGS:
            print("- " + tag)
        print("Impact levels:")
        for level, description in IMPACT_LEVELS.items():
            print("- {}: {}".format(level, description))
        return 0
    if args.domain == "metrics" and args.operation == "review":
        start = "{}-01-01".format(date.today().year)
        end = date.today().isoformat()
        from .metrics.reports import build_report
        summary = build_report(Path(args.repo), start, end)
        print("GTD review")
        print("Tasks with records: {}".format(summary["task_count"]))
        print("Completed tasks: {}".format(summary["completed_count"]))
        print("Active hours: {:.2f}".format(summary["active_seconds"] / 3600.0))
        print("Waiting hours: {:.2f}".format(summary["waiting_seconds"] / 3600.0))
        print("Scheduled hours: {:.2f}".format(summary["scheduled_seconds"] / 3600.0))
        print("Data errors: {}".format(len(summary["read_errors"])))
        return 1 if summary["read_errors"] else 0
    if args.domain != "gtd" or args.operation not in ("dispatch", "task"):
        _parser().print_help()
        return 2
    repo = Path(args.repo)
    gtd_path = Path(args.gtd_file) if args.gtd_file else repo / "gtd.md"
    try:
        if args.operation == "dispatch":
            result = dispatch(repo, gtd_path, args.machine_id)
            print(json.dumps({
                "gtd_path": str(result.gtd_path),
                "moved": result.moved,
                "created": [str(path) for path in result.created],
                "event_count": result.event_count,
            }, ensure_ascii=False, sort_keys=True))
        else:
            print(str(create_task(repo, args.line, gtd_path)))
        return 0
    except DispatchError as error:
        if args.operation == "dispatch":
            print("GTD: dispatch failed", file=sys.stderr)
        else:
            print("GTD: task failed", file=sys.stderr)
        print(str(error), file=sys.stderr)
        return 1
