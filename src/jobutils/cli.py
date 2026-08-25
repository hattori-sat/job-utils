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
from .gitops import (
    GitOperationError,
    commit as git_commit,
    push as git_push,
    push_mock,
    status as git_status,
)
from .gtd import (
    DocumentError,
    DispatchError,
    create_document,
    create_subdocument,
    create_subtask,
    create_task,
    dispatch,
)
from .metrics.catalog import DEFAULT_TAGS, IMPACT_LEVELS
from .metrics.events import append_work_started, append_work_stopped
from .metrics.reader import read_events
from .metrics.reports import write_reports
from .markdown.images import ClipboardError, paste_clipboard_image
from .markdown.formatter import FormatError, format_file
from .setup_workflow import SetupError, run_setup
from .sync.adapters import AtlassianHttpAdapter, MemoryAdapter
from .sync.engine import (
    SyncError,
    apply_plan,
    check,
    create_plan,
    pull,
    rebind,
    save_plan,
    sync_status,
)


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
    task_parser.add_argument("--parent", default=None)
    subtask_parser = gtd_subparsers.add_parser("subtask")
    subtask_parser.add_argument("--repo", default=".")
    subtask_parser.add_argument("--parent", required=True)
    subtask_parser.add_argument("--line", type=int, required=True)
    document_parser = gtd_subparsers.add_parser("document")
    document_parser.add_argument("--repo", default=".")
    document_parser.add_argument("--docs-file", default=None)
    document_parser.add_argument("--line", type=int, required=True)
    subdocument_parser = gtd_subparsers.add_parser("subdocument")
    subdocument_parser.add_argument("--repo", default=".")
    subdocument_parser.add_argument("--parent", required=True)
    subdocument_parser.add_argument("--line", type=int, required=True)
    markdown = subparsers.add_parser("markdown")
    markdown_subparsers = markdown.add_subparsers(dest="operation")
    format_parser = markdown_subparsers.add_parser("format")
    format_parser.add_argument("--path", required=True)
    format_parser.add_argument("--check", action="store_true")
    paste_image_parser = markdown_subparsers.add_parser("paste-image")
    paste_image_parser.add_argument("--repo", default=".")
    paste_image_parser.add_argument("--file", required=True)
    paste_image_parser.add_argument("--name", default=None)
    paste_image_parser.add_argument(
        "--provider",
        choices=(
            "auto",
            "pngpaste",
            "osascript",
            "powershell",
            "pwsh",
            "wl-paste",
            "xclip",
        ),
        default="auto",
    )
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
    start_parser = metrics_subparsers.add_parser("start")
    start_parser.add_argument("--repo", default=".")
    start_parser.add_argument("--gtd-id", required=True)
    start_parser.add_argument("--at", default=None)
    start_parser.add_argument("--machine-id", default=None)
    stop_parser = metrics_subparsers.add_parser("stop")
    stop_parser.add_argument("--repo", default=".")
    stop_parser.add_argument("--gtd-id", required=True)
    stop_parser.add_argument("--at", default=None)
    stop_parser.add_argument("--machine-id", default=None)
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
    apply_parser.add_argument(
        "--git-sync",
        dest="git_sync",
        action="store_true",
        help="commit and push local sync metadata after apply",
    )
    apply_parser.add_argument(
        "--no-git-sync",
        dest="git_sync",
        action="store_false",
        help="apply externally without committing or pushing local sync metadata",
    )
    apply_parser.set_defaults(git_sync=None)
    apply_parser.add_argument(
        "--commit-message",
        default="chore: synchronize GTD repository",
    )
    apply_parser.add_argument("--remote", default="origin")
    apply_parser.add_argument("--branch", default="")
    apply_parser.add_argument("--set-upstream", action="store_true")
    pull_parser = sync_subparsers.add_parser("pull")
    pull_parser.add_argument("--repo", default=".")
    pull_parser.add_argument(
        "--adapter", choices=("memory", "atlassian"), default="atlassian"
    )
    check_parser = sync_subparsers.add_parser("check")
    check_parser.add_argument("--repo", default=".")
    check_parser.add_argument(
        "--adapter", choices=("memory", "atlassian"), default="atlassian"
    )
    rebind_parser = sync_subparsers.add_parser("rebind")
    rebind_parser.add_argument("--repo", default=".")
    rebind_parser.add_argument("--path", required=True)
    rebind_parser.add_argument("--kind", choices=("jira", "confluence"), required=True)
    rebind_parser.add_argument("--external-id", required=True)
    rebind_parser.add_argument("--url", default=None)
    rebind_parser.add_argument("--parent-id", default=None)
    sync_subparsers.add_parser("status").add_argument("--repo", default=".")
    git = subparsers.add_parser("git")
    git_subparsers = git.add_subparsers(dest="operation")
    git_status_parser = git_subparsers.add_parser("status")
    git_status_parser.add_argument("--repo", default=".")
    git_commit_parser = git_subparsers.add_parser("commit")
    git_commit_parser.add_argument("--repo", default=".")
    git_commit_parser.add_argument("--message", required=True)
    git_push_parser = git_subparsers.add_parser("push-mock")
    git_push_parser.add_argument("--repo", default=".")
    git_push_parser.add_argument("--remote", default="mock-origin")
    git_push_parser.add_argument("--branch", default="")
    git_push_parser.add_argument(
        "--remote-url", default="mock://github/local-gtd-repository"
    )
    git_real_push_parser = git_subparsers.add_parser("push")
    git_real_push_parser.add_argument("--repo", default=".")
    git_real_push_parser.add_argument("--remote", default="origin")
    git_real_push_parser.add_argument("--branch", default="")
    git_real_push_parser.add_argument("--set-upstream", action="store_true")
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
                gtd_repo = input(
                    "Enter the path to an existing local Git Repository directory: "
                )
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
    if args.domain == "markdown" and args.operation == "paste-image":
        try:
            markdown_file = Path(args.file)
            if not markdown_file.is_absolute():
                markdown_file = Path(args.repo) / markdown_file
            result = paste_clipboard_image(
                markdown_file,
                alt_text=args.name,
                provider=args.provider,
            )
            print("image: {}".format(result["image_path"]))
            print("markdown: {}".format(result["markdown"]))
            return 0
        except (ClipboardError, OSError, ValueError) as error:
            print("IMAGE: paste failed: {}".format(error), file=sys.stderr)
            return 1
    if args.domain == "markdown" and args.operation == "format":
        try:
            changed = format_file(Path(args.path), check=args.check)
            if args.check and changed:
                print("MARKDOWN: formatting required: {}".format(args.path), file=sys.stderr)
                return 1
            if args.check:
                print("ok: {}".format(args.path))
                return 0
            print("markdown formatted: {}".format(args.path))
            return 0
        except (FormatError, OSError, ValueError) as error:
            print("MARKDOWN: format failed: {}".format(error), file=sys.stderr)
            return 1
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
    if args.domain == "git":
        try:
            repo = Path(args.repo)
            if args.operation == "status":
                print(git_status(repo), end="")
                return 0
            if args.operation == "commit":
                print(json.dumps(git_commit(repo, args.message), sort_keys=True))
                return 0
            if args.operation == "push-mock":
                print(
                    json.dumps(
                        push_mock(
                            repo,
                            remote=args.remote,
                            branch=args.branch,
                            remote_url=args.remote_url,
                        ),
                        sort_keys=True,
                    )
                )
                return 0
            if args.operation == "push":
                print(
                    json.dumps(
                        git_push(
                            repo,
                            remote=args.remote,
                            branch=args.branch,
                            set_upstream=args.set_upstream,
                        ),
                        sort_keys=True,
                    )
                )
                return 0
        except GitOperationError as error:
            print("GIT: operation failed: {}".format(error), file=sys.stderr)
            return 1
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
        print("Lead hours: {:.2f}".format(summary["lead_seconds"] / 3600.0))
        print("Cycle hours: {:.2f}".format(summary["cycle_seconds"] / 3600.0))
        print(
            "Top tags: {}".format(
                ", ".join(
                    sorted(
                        summary["by_tag"],
                        key=lambda tag: summary["by_tag"][tag]["task_count"],
                        reverse=True,
                    )[:5]
                )
                or "none"
            )
        )
        print("Data errors: {}".format(len(summary["read_errors"])))
        return 1 if summary["read_errors"] else 0
    if args.domain == "metrics" and args.operation == "start":
        append_work_started(
            Path(args.repo),
            args.gtd_id,
            machine_id=args.machine_id,
            occurred_at=args.at,
        )
        print("work started: {}".format(args.gtd_id))
        return 0
    if args.domain == "metrics" and args.operation == "stop":
        append_work_stopped(
            Path(args.repo),
            args.gtd_id,
            machine_id=args.machine_id,
            occurred_at=args.at,
        )
        print("work stopped: {}".format(args.gtd_id))
        return 0
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
    if args.domain == "sync" and args.operation == "status":
        print(json.dumps(sync_status(Path(args.repo)), sort_keys=True))
        return 0
    if args.domain == "sync" and args.operation == "apply":
        try:
            repo = Path(args.repo)
            git_sync = (
                args.git_sync
                if args.git_sync is not None
                else args.adapter == "atlassian"
            )
            if git_sync and git_status(repo).strip():
                raise GitOperationError(
                    "working tree must be clean before sync apply with Git synchronization"
                )
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
            results = apply_plan(repo, plan, adapter)
            response = {"actions": results}
            if git_sync:
                commit_result = None
                if git_status(repo).strip():
                    commit_result = git_commit(repo, args.commit_message)
                response["git"] = {
                    "commit": commit_result,
                    "push": git_push(
                        repo,
                        remote=args.remote,
                        branch=args.branch,
                        set_upstream=args.set_upstream,
                    ),
                }
            print(json.dumps(response, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        except (OSError, ValueError, SyncError, RuntimeError, GitOperationError) as error:
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
    if args.domain == "sync" and args.operation == "rebind":
        try:
            path = rebind(
                Path(args.repo),
                args.path,
                args.kind,
                args.external_id,
                args.url,
                args.parent_id,
            )
            print(str(path))
            return 0
        except (OSError, SyncError, ValueError) as error:
            print("SYNC: rebind failed: {}".format(error), file=sys.stderr)
            return 1
    if args.domain == "sync" and args.operation == "check":
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
            result = check(Path(args.repo), adapter)
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            if result["error_count"]:
                print(
                    "SYNC: check failed: {} item(s) could not be checked".format(
                        result["error_count"]
                    ),
                    file=sys.stderr,
                )
                return 1
            return 0
        except (OSError, ValueError, SyncError, RuntimeError, KeyError) as error:
            print("SYNC: check failed: {}".format(error), file=sys.stderr)
            return 1
    if args.domain != "gtd" or args.operation not in (
        "dispatch",
        "task",
        "subtask",
        "document",
        "subdocument",
        ):
        _parser().print_help()
        return 2
    repo = Path(args.repo)
    gtd_path = (
        Path(args.gtd_file) if getattr(args, "gtd_file", None) else repo / "gtd.md"
    )
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
        elif args.operation == "task":
            print(str(create_task(repo, args.line, gtd_path, args.parent)))
        elif args.operation == "subtask":
            print(str(create_subtask(repo, args.parent, args.line)))
        elif args.operation == "document":
            docs_path = Path(args.docs_file) if args.docs_file else repo / "docs.md"
            print(str(create_document(repo, args.line, docs_path)))
        else:
            print(str(create_subdocument(repo, args.parent, args.line)))
        return 0
    except (DispatchError, DocumentError) as error:
        if args.operation == "dispatch":
            print("GTD: dispatch failed", file=sys.stderr)
        elif args.operation == "task":
            print("GTD: task failed", file=sys.stderr)
        elif args.operation == "subtask":
            print("GTD: subtask failed", file=sys.stderr)
        elif args.operation == "subdocument":
            print("GTD: subdocument failed", file=sys.stderr)
        else:
            print("GTD: document failed", file=sys.stderr)
        print(str(error), file=sys.stderr)
        return 1
