"""Command-line entry points for GTD, metrics, and synchronization tasks."""

import argparse
from datetime import date
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

from .config import validate_config
from .env import load_local_env
from .gtd import DispatchError, create_task, dispatch
from .metrics.catalog import DEFAULT_TAGS, IMPACT_LEVELS
from .metrics.reader import read_events
from .metrics.reports import write_reports
from .setup_workflow import SetupError, run_setup
from .sync.adapters import AtlassianHttpAdapter, MemoryAdapter
from .sync.engine import SyncError, apply_plan, create_plan, pull, save_plan


def _parser() -> argparse.ArgumentParser:
    """Build the cross-platform command-line parser."""

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
    sync = subparsers.add_parser("sync")
    sync_subparsers = sync.add_subparsers(dest="operation")
    plan_parser = sync_subparsers.add_parser("plan")
    plan_parser.add_argument("--repo", default=".")
    plan_parser.add_argument("--output", default=None)
    apply_parser = sync_subparsers.add_parser("apply")
    apply_parser.add_argument("--repo", default=".")
    apply_parser.add_argument("--plan", required=True)
    apply_parser.add_argument(
        "--adapter", choices=("memory", "atlassian"), default="memory"
    )
    pull_parser = sync_subparsers.add_parser("pull")
    pull_parser.add_argument("--repo", default=".")
    pull_parser.add_argument(
        "--adapter", choices=("memory", "atlassian"), default="atlassian"
    )
    config = subparsers.add_parser("config")
    config_subparsers = config.add_subparsers(dest="operation")
    config_validate_parser = config_subparsers.add_parser("validate")
    config_validate_parser.add_argument("--path", default="config.yaml")
    setup = subparsers.add_parser("setup")
    setup_subparsers = setup.add_subparsers(dest="operation")
    setup_init = setup_subparsers.add_parser("init")
    setup_init.add_argument("--job-utils-root", default=".")
    setup_init.add_argument("--gtd-repo", default=None)
    setup_init.add_argument("--platform", default=None)
    setup_init.add_argument("--skip-env-prompt", action="store_true")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Execute a command and return a shell-compatible exit status."""

    load_local_env(Path(__file__).resolve().parents[2])
    args = _parser().parse_args(argv)
    if args.domain == "setup" and args.operation == "init":
        try:
            gtd_repo = args.gtd_repo
            if not gtd_repo:
                gtd_repo = input("Enter the path to an existing empty Git Repository: ")
            result = run_setup(
                Path(args.job_utils_root),
                Path(gtd_repo),
                platform_name=args.platform,
                skip_env_prompt=args.skip_env_prompt,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            print("setup complete")
            return 0
        except (OSError, SetupError, ValueError) as error:
            print("SETUP: failed: {}".format(error), file=sys.stderr)
            return 1
    if args.domain == "config" and args.operation == "validate":
        errors = validate_config(Path(args.path))
        for error in errors:
            print("CONFIG: " + error, file=sys.stderr)
        if errors:
            return 1
        print("config valid: {}".format(args.path))
        return 0
    if args.domain == "metrics" and args.operation == "report":
        formats = [value.strip() for value in args.format.split(",") if value.strip()]
        output_dir = Path(args.output_dir) if args.output_dir else None
        paths = write_reports(
            Path(args.repo), args.start, args.end, formats, output_dir
        )
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
    if args.domain == "sync" and args.operation == "plan":
        plan = create_plan(Path(args.repo))
        path = Path(args.output) if args.output else save_plan(Path(args.repo), plan)
        if args.output:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        print(path)
        print(
            json.dumps(
                {"plan_id": plan["plan_id"], "actions": len(plan["actions"])},
                sort_keys=True,
            )
        )
        return 0
    if args.domain == "sync" and args.operation == "apply":
        try:
            plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
            if args.adapter == "memory":
                adapter = MemoryAdapter()
            else:
                adapter = AtlassianHttpAdapter(
                    {
                        "jira_base_url": os.environ.get("JIRA_BASE_URL", ""),
                        "confluence_base_url": os.environ.get(
                            "CONFLUENCE_BASE_URL", ""
                        ),
                    }
                )
            results = apply_plan(Path(args.repo), plan, adapter)
            print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        except (OSError, ValueError, SyncError, RuntimeError) as error:
            print("SYNC: apply failed: {}".format(error), file=sys.stderr)
            return 1
    if args.domain == "sync" and args.operation == "pull":
        try:
            if args.adapter == "memory":
                adapter = MemoryAdapter()
            else:
                adapter = AtlassianHttpAdapter(
                    {
                        "jira_base_url": os.environ.get("JIRA_BASE_URL", ""),
                        "confluence_base_url": os.environ.get(
                            "CONFLUENCE_BASE_URL", ""
                        ),
                    }
                )
            print(
                json.dumps(
                    pull(Path(args.repo), adapter),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        except (OSError, ValueError, SyncError, RuntimeError, KeyError) as error:
            print("SYNC: pull failed: {}".format(error), file=sys.stderr)
            return 1
    if args.domain != "gtd" or args.operation not in ("dispatch", "task"):
        _parser().print_help()
        return 2
    repo = Path(args.repo)
    gtd_path = Path(args.gtd_file) if args.gtd_file else repo / "gtd.md"
    try:
        if args.operation == "dispatch":
            result = dispatch(repo, gtd_path, args.machine_id)
            print(
                json.dumps(
                    {
                        "gtd_path": str(result.gtd_path),
                        "moved": result.moved,
                        "created": [str(path) for path in result.created],
                        "event_count": result.event_count,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
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
