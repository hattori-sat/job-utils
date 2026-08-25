"""Explicit local Git helpers with no real remote push operation."""

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List

from .metrics.events import append_event


class GitOperationError(Exception):
    """A local Git operation could not be completed safely."""


def _redact_git_output(value: str) -> str:
    """Remove credentials if Git includes an authenticated URL in output."""

    return re.sub(
        r"(?i)(https?://)[^/\s@]+:[^/\s@]+@",
        r"\1<credentials>@",
        value,
    )


def _validate_git_argument(value: str, label: str) -> str:
    """Reject option-like or whitespace-containing remote/ref arguments."""

    value = str(value or "").strip()
    if not value or value.startswith("-") or any(char.isspace() for char in value):
        raise GitOperationError("{} must be a non-empty Git name".format(label))
    return value


def _run(repo_root: Path, arguments: List[str]) -> subprocess.CompletedProcess:
    """Run Git without a shell and capture text output."""

    return subprocess.run(
        ["git"] + arguments,
        cwd=str(repo_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def status(repo_root: Path) -> str:
    """Return porcelain status for the selected local repository."""

    result = _run(Path(repo_root).resolve(), ["status", "--porcelain"])
    if result.returncode:
        raise GitOperationError(result.stderr.strip() or "git status failed")
    return result.stdout


def _unsafe_paths(output: str) -> List[str]:
    """Return staged paths that look like credentials or private keys."""

    paths = []
    for line in output.splitlines():
        path = line.strip()
        if not path:
            continue
        name = Path(path).name.lower()
        lowered = path.lower()
        if (
            name in (".env", ".env.local", ".env.production")
            or name.endswith((".pem", ".key", ".p12", ".pfx"))
            or "private-key" in lowered
            or "id_rsa" in lowered
        ):
            paths.append(path)
    return paths


def commit(repo_root: Path, message: str) -> Dict[str, str]:
    """Commit local changes after recording an auditable intent event.

    The helper invokes only local Git commands. It never invokes a remote or
    push command, and it rejects credential-shaped files before committing.
    """

    repo_root = Path(repo_root).resolve()
    if not message.strip():
        raise GitOperationError("commit message cannot be empty")
    current_status = status(repo_root)
    if not current_status.strip():
        raise GitOperationError("working tree is clean")

    staged = _run(repo_root, ["add", "-A"])
    if staged.returncode:
        raise GitOperationError(staged.stderr.strip() or "git add failed")

    staged_paths = _run(repo_root, ["diff", "--cached", "--name-only"])
    if staged_paths.returncode:
        raise GitOperationError(staged_paths.stderr.strip() or "git diff failed")
    unsafe = _unsafe_paths(staged_paths.stdout)
    if unsafe:
        _run(repo_root, ["reset", "--", *unsafe])
        raise GitOperationError(
            "refusing to commit credential-shaped files: {}".format(
                ", ".join(unsafe)
            )
        )

    append_event(
        repo_root,
        "git_commit_intent",
        "repository",
        source={
            "machine_id": os.environ.get("JOBUTILS_MACHINE_ID", "unknown"),
            "command": "git commit",
        },
        message=message,
        changed_files=current_status.splitlines(),
    )
    staged = _run(repo_root, ["add", "-A"])
    if staged.returncode:
        raise GitOperationError(staged.stderr.strip() or "git add failed")
    result = _run(repo_root, ["commit", "-m", message])
    if result.returncode:
        raise GitOperationError(result.stderr.strip() or "git commit failed")
    revision = _run(repo_root, ["rev-parse", "HEAD"])
    if revision.returncode:
        raise GitOperationError(revision.stderr.strip() or "could not read commit")
    return {"revision": revision.stdout.strip(), "message": message}


def push(
    repo_root: Path,
    remote: str = "origin",
    branch: str = "",
    set_upstream: bool = False,
) -> Dict[str, object]:
    """Push a clean local branch to an existing configured Git remote.

    Authentication is delegated to Git's configured credential helper or SSH
    agent. The operation never invokes a shell and never force-pushes.
    """

    repo_root = Path(repo_root).resolve()
    if status(repo_root).strip():
        raise GitOperationError("working tree must be clean before push")
    selected_remote = _validate_git_argument(remote, "remote")
    remote_result = _run(repo_root, ["remote", "get-url", selected_remote])
    if remote_result.returncode:
        raise GitOperationError(
            _redact_git_output(
                remote_result.stderr.strip() or "configured remote was not found"
            )
        )
    current_branch = _run(repo_root, ["branch", "--show-current"])
    if current_branch.returncode:
        raise GitOperationError(
            _redact_git_output(
                current_branch.stderr.strip() or "could not determine branch"
            )
        )
    selected_branch = _validate_git_argument(
        branch or current_branch.stdout.strip(), "branch"
    )
    arguments = ["push"]
    if set_upstream:
        arguments.append("--set-upstream")
    arguments.extend([selected_remote, selected_branch])
    result = _run(repo_root, arguments)
    if result.returncode:
        raise GitOperationError(
            _redact_git_output(result.stderr.strip() or "git push failed")
        )
    revision = _run(repo_root, ["rev-parse", "HEAD"])
    if revision.returncode:
        raise GitOperationError(
            _redact_git_output(
                revision.stderr.strip() or "could not determine revision"
            )
        )
    return {
        "performed": True,
        "remote": selected_remote,
        "branch": selected_branch,
        "revision": revision.stdout.strip(),
        "output": _redact_git_output(
            "\n".join(value for value in (result.stdout, result.stderr) if value)
        ).strip(),
    }


def pull(
    repo_root: Path,
    remote: str = "origin",
    branch: str = "",
) -> Dict[str, object]:
    """Fast-forward a clean local branch from its configured Git remote."""

    repo_root = Path(repo_root).resolve()
    if status(repo_root).strip():
        raise GitOperationError("working tree must be clean before pull")
    selected_remote = _validate_git_argument(remote, "remote")
    remote_result = _run(repo_root, ["remote", "get-url", selected_remote])
    if remote_result.returncode:
        raise GitOperationError(
            _redact_git_output(
                remote_result.stderr.strip() or "configured remote was not found"
            )
        )
    current_branch = _run(repo_root, ["branch", "--show-current"])
    if current_branch.returncode:
        raise GitOperationError(
            _redact_git_output(
                current_branch.stderr.strip() or "could not determine branch"
            )
        )
    selected_branch = _validate_git_argument(
        branch or current_branch.stdout.strip(), "branch"
    )
    result = _run(
        repo_root,
        ["pull", "--ff-only", selected_remote, selected_branch],
    )
    if result.returncode:
        raise GitOperationError(
            _redact_git_output(result.stderr.strip() or "git pull failed")
        )
    revision = _run(repo_root, ["rev-parse", "HEAD"])
    if revision.returncode:
        raise GitOperationError(
            _redact_git_output(
                revision.stderr.strip() or "could not determine revision"
            )
        )
    return {
        "performed": True,
        "remote": selected_remote,
        "branch": selected_branch,
        "revision": revision.stdout.strip(),
        "output": _redact_git_output(
            "\n".join(value for value in (result.stdout, result.stderr) if value)
        ).strip(),
    }


def push_mock(
    repo_root: Path,
    remote: str = "mock-origin",
    branch: str = "",
    remote_url: str = "mock://github/local-gtd-repository",
) -> Dict[str, object]:
    """Describe a push without invoking or configuring a Git remote."""

    repo_root = Path(repo_root).resolve()
    if status(repo_root).strip():
        raise GitOperationError("working tree must be clean before push simulation")
    current_branch = _run(repo_root, ["branch", "--show-current"])
    if current_branch.returncode:
        raise GitOperationError(
            current_branch.stderr.strip() or "could not determine branch"
        )
    revision = _run(repo_root, ["rev-parse", "HEAD"])
    if revision.returncode:
        raise GitOperationError(
            revision.stderr.strip() or "could not determine revision"
        )
    selected_branch = branch or current_branch.stdout.strip()
    if not selected_branch:
        raise GitOperationError("branch is required for push simulation")
    return {
        "performed": False,
        "remote": remote,
        "remote_url": remote_url,
        "branch": selected_branch,
        "revision": revision.stdout.strip(),
        "command": ["git", "push", remote, selected_branch],
    }
