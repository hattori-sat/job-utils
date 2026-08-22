import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from .gtd import DispatchError, create_task, dispatch


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
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
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

