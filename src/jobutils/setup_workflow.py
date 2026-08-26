"""Resumable, non-destructive setup workflow for job-utils."""

import getpass
import json
import os
import platform as platform_module
import shutil
import stat
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional


class SetupError(RuntimeError):
    """A setup prerequisite or safe-write operation failed."""


SUPPORTED_PLATFORMS = ("macos", "ubuntu", "windows")
ENV_SPECS = (
    ("JIRA_BASE_URL", "Jira base URL", False, "https://your-domain.atlassian.net"),
    ("JIRA_EMAIL", "Jira account email", False, ""),
    ("JIRA_API_TOKEN", "Jira API token", True, ""),
    ("JIRA_PROJECT", "Jira project key", False, ""),
    ("JIRA_ISSUE_TYPE", "Jira issue type", False, "Task"),
    (
        "JIRA_PROGRESS_COMMENT_FIELD",
        "Jira Progress Comment field id",
        False,
        "",
    ),
    (
        "JIRA_PROGRESS_COMMENT_FORMAT",
        "Jira Progress Comment format (text or adf)",
        False,
        "text",
    ),
    (
        "CONFLUENCE_BASE_URL",
        "Confluence base URL",
        False,
        "https://your-domain.atlassian.net",
    ),
    ("CONFLUENCE_EMAIL", "Confluence account email", False, ""),
    ("CONFLUENCE_API_TOKEN", "Confluence API token", True, ""),
    ("CONFLUENCE_SPACE_ID", "Confluence space id", False, ""),
    ("CONFLUENCE_SPACE_KEY", "Confluence space key", False, ""),
    ("CONFLUENCE_PARENT_ID", "Confluence parent page id", False, ""),
)

GTD_TEMPLATE = """# GTD

## Inbox

## Next Actions

## Today

## Focus

## Waiting

## Calendar

## Someday

## Projects

## Done
"""
DOCUMENTS_TEMPLATE = "# Documents\n"
BEGIN_MARKER = "# >>> job-utils setup >>>"
END_MARKER = "# <<< job-utils setup <<<"
GTD_GITIGNORE_BLOCK = "\n".join(
    [
        "# >>> job-utils setup >>>",
        ".jobutils/output/",
        ".jobutils/sync/plans/",
        "*.swp",
        "*.swo",
        "# <<< job-utils setup <<<",
    ]
)
VIM_BEGIN_MARKER = '" >>> job-utils setup >>>'
VIM_END_MARKER = '" <<< job-utils setup <<<'


@dataclass(frozen=True)
class SetupPaths:
    """Paths used by one setup run."""

    job_utils_root: Path
    gtd_repo: Path
    platform_name: str
    home: Path

    @property
    def venv_root(self) -> Path:
        return self.job_utils_root / ".venv"

    @property
    def venv_python(self) -> Path:
        if self.platform_name == "windows":
            return self.venv_root / "Scripts" / "python.exe"
        return self.venv_root / "bin" / "python"

    @property
    def user_bin(self) -> Path:
        if self.platform_name == "windows":
            return self.home / "bin"
        return self.home / ".local" / "bin"

    @property
    def state_root(self) -> Path:
        return self.job_utils_root / ".jobutils" / "setup"


def detect_platform(
    system: Optional[str] = None, distribution: Optional[str] = None
) -> str:
    """Map host identifiers to the supported setup platforms."""

    system = system or platform_module.system()
    if system == "Darwin":
        return "macos"
    if system == "Windows":
        return "windows"
    if system == "Linux":
        value = (distribution or _linux_distribution()).lower()
        if "ubuntu" in value:
            return "ubuntu"
    raise SetupError(
        "unsupported platform: {} (supported: macOS, Ubuntu, Windows)".format(
            system
        )
    )


def _linux_distribution() -> str:
    """Read Linux distribution identifiers without a third-party package."""

    release = Path("/etc/os-release")
    if not release.is_file():
        return ""
    return release.read_text(encoding="utf-8", errors="replace").lower()


def validate_gtd_repository(path: Path) -> Path:
    """Validate an existing local non-bare Git Repository directory."""

    path = Path(path).expanduser().resolve()
    if not path.exists():
        raise SetupError("GTD Git Repository path does not exist: {}".format(path))
    if not path.is_dir():
        raise SetupError("GTD Git Repository path is not a directory: {}".format(path))
    git_metadata = path / ".git"
    if not git_metadata.exists():
        raise SetupError("GTD path is not a Git Repository: {}".format(path))
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
    except OSError as error:
        raise SetupError("Git is required to validate the GTD Repository") from error
    if result.returncode != 0 or result.stdout.strip().lower() != "true":
        raise SetupError("GTD path is not a valid Git Repository: {}".format(path))
    return path


def _write_if_missing(path: Path, content: str) -> bool:
    """Create one file only when it does not already exist."""

    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _ensure_index_link(path: Path, link: str) -> bool:
    """Add one reciprocal index link without replacing existing content."""

    lines = path.read_text(encoding="utf-8").splitlines()
    if link in lines:
        return False
    heading = next(
        (index for index, line in enumerate(lines) if line.startswith("# ")),
        None,
    )
    if heading is None:
        lines = [link, ""] + lines
    else:
        lines[heading + 1 : heading + 1] = ["", link]
    path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    return True


def bootstrap_gtd_repository(path: Path) -> List[str]:
    """Create missing GTD Repository indexes and runtime directories safely."""

    path = validate_gtd_repository(path)
    created = []
    if _write_if_missing(path / "gtd.md", GTD_TEMPLATE):
        created.append("gtd.md")
    if _write_if_missing(path / "docs.md", DOCUMENTS_TEMPLATE):
        created.append("docs.md")
    if _ensure_index_link(path / "gtd.md", "[Documents](docs.md)"):
        created.append("gtd.md link")
    if _ensure_index_link(path / "docs.md", "[GTD](gtd.md)"):
        created.append("docs.md link")
    gitignore = path / ".gitignore"
    existing_gitignore = (
        gitignore.read_text(encoding="utf-8") if gitignore.is_file() else ""
    )
    updated_gitignore = _replace_managed_block(existing_gitignore, GTD_GITIGNORE_BLOCK)
    if updated_gitignore != existing_gitignore:
        gitignore.write_text(updated_gitignore, encoding="utf-8")
        created.append(".gitignore")
    for relative in (
        "gtd_tasks",
        "documents",
        ".jobutils",
        ".jobutils/metrics/events",
        ".jobutils/output",
    ):
        directory = path / relative
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            created.append(relative + "/")
    return created


def _has_git_commit(path: Path) -> bool:
    """Return whether a local Git repository has an initial commit."""

    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--verify", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _git_worktree_status(path: Path) -> str:
    """Return the selected repository's porcelain status."""

    result = subprocess.run(
        ["git", "-C", str(path), "status", "--porcelain"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SetupError(
            "could not inspect the GTD repository: {}".format(
                result.stderr.strip() or "git status failed"
            )
        )
    return result.stdout


def ensure_gtd_setup_commit(path: Path, status_before_setup: str) -> Dict[str, str]:
    """Commit setup changes locally without absorbing pre-existing changes."""

    path = validate_gtd_repository(path)
    status_after_setup = _git_worktree_status(path)
    if not status_after_setup.strip():
        return {"status": "unchanged"}
    if _has_git_commit(path) and status_before_setup.strip():
        return {"status": "skipped_dirty"}

    from .gitops import GitOperationError, commit

    try:
        result = commit(path, "chore: initialize GTD repository")
    except GitOperationError as error:
        raise SetupError(
            "could not create the GTD setup commit: {}".format(error)
        ) from error
    return {"status": "created", "revision": result["revision"]}


def _parse_env(lines: Iterable[str]) -> Dict[str, str]:
    """Parse simple KEY=value entries without evaluating shell syntax."""

    result = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        result[key.strip()] = value.strip().strip("'\"")
    return result


def _set_env_value(lines: List[str], key: str, value: str) -> None:
    """Replace a simple environment assignment or append one."""

    replacement = "{}={}".format(key, value)
    for index, line in enumerate(lines):
        if line.startswith(key + "="):
            lines[index] = replacement
            return
    lines.append(replacement)


def ensure_env_file(
    job_utils_root: Path,
    input_fn: Callable[[str], str] = input,
    secret_input_fn: Callable[[str], str] = getpass.getpass,
) -> Path:
    """Create or complete the ignored `.env` file through prompts."""

    root = Path(job_utils_root).resolve()
    example = root / ".env.example"
    env_path = root / ".env"
    if not example.is_file():
        raise SetupError(".env.example was not found: {}".format(example))
    source = env_path.read_text(encoding="utf-8") if env_path.is_file() else example.read_text(encoding="utf-8")
    lines = source.splitlines()
    values = _parse_env(lines)
    for key, label, secret, default in ENV_SPECS:
        current = values.get(key, "")
        placeholder = current in ("", "YOUR_ATLASSIAN_EMAIL") or current.startswith(
            "https://your-domain"
        )
        if not placeholder:
            continue
        prompt = "{} [{}]: ".format(label, default) if default else "{}: ".format(label)
        answer = secret_input_fn(prompt) if secret else input_fn(prompt)
        answer = answer.strip()
        if not answer and default:
            answer = default
        if answer:
            _set_env_value(lines, key, answer)
    env_path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    if os.name != "nt":
        env_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return env_path


def _replace_managed_block(
    existing: str,
    block: str,
    begin_marker: str = BEGIN_MARKER,
    end_marker: str = END_MARKER,
) -> str:
    """Replace or append one idempotent setup block."""

    start = existing.find(begin_marker)
    end = existing.find(end_marker)
    if start >= 0 and end >= start:
        end += len(end_marker)
        pieces = []
        before = existing[:start].rstrip("\n")
        after = existing[end:].lstrip("\n")
        if before:
            pieces.append(before)
        pieces.append(block)
        if after:
            pieces.append(after)
        return "\n\n".join(pieces) + "\n"
    if existing.strip():
        return existing.rstrip("\n") + "\n\n" + block + "\n"
    return block + "\n"


def _write_managed_file(path: Path, content: str, marker: str) -> None:
    """Write generated content without replacing an unmanaged user file."""

    if path.is_file():
        existing = path.read_text(encoding="utf-8")
        if marker not in existing:
            raise SetupError("refusing to overwrite unmanaged file: {}".format(path))
        if existing == content:
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _vim_path(path: Path) -> str:
    """Return a Vim-safe single-quoted path."""

    return str(path.expanduser()).replace("\\", "/").replace("'", "''")


def ensure_vimrc_registration(
    vimrc_path: Path, snippet_path: Path, python_path: str, job_utils_root: Optional[Path] = None
) -> Path:
    """Write a local Vim snippet and register it once in the user's Vimrc."""

    vimrc_path = Path(vimrc_path).expanduser()
    snippet_path = Path(snippet_path).expanduser()
    root = Path(job_utils_root or snippet_path.parent.parent).resolve()
    snippet_path.parent.mkdir(parents=True, exist_ok=True)
    snippet = "\n".join(
        [
            '" Generated by job-utils setup.',
            "if exists('g:jobutils_setup_loaded') | finish | endif",
            "let g:jobutils_setup_loaded = 1",
            "execute 'set runtimepath^=' . fnameescape('{}')".format(
                _vim_path(root / "vim")
            ),
            "let g:jobutils_python = '{}'".format(_vim_path(Path(python_path))),
            "",
        ]
    )
    _write_managed_file(snippet_path, snippet, '" Generated by job-utils setup.')
    block = "\n".join(
        [
            VIM_BEGIN_MARKER,
            "execute 'source ' . fnameescape('{}')".format(_vim_path(snippet_path)),
            VIM_END_MARKER,
        ]
    )
    existing = vimrc_path.read_text(encoding="utf-8") if vimrc_path.is_file() else ""
    # Older setup runs used shell-style markers in Vimrc. Normalize complete
    # marker lines before replacing the managed block so rerunning setup also
    # repairs malformed lines such as ``>>> job-utils setup >>>: # ...``.
    normalized_lines = []
    for line in existing.splitlines():
        if BEGIN_MARKER in line:
            normalized_lines.append(VIM_BEGIN_MARKER)
        elif END_MARKER in line:
            normalized_lines.append(VIM_END_MARKER)
        else:
            normalized_lines.append(line)
    existing = "\n".join(normalized_lines)
    if existing:
        existing += "\n"
    vimrc_path.parent.mkdir(parents=True, exist_ok=True)
    vimrc_path.write_text(
        _replace_managed_block(
            existing, block, VIM_BEGIN_MARKER, VIM_END_MARKER
        ),
        encoding="utf-8",
    )
    return vimrc_path


def _posix_wrapper(
    python_path: Path,
    source_path: Path,
    command: str,
    gtd_repo: Optional[Path] = None,
) -> str:
    """Render one POSIX user wrapper."""

    quoted = str(python_path.expanduser()).replace("'", "'\\''")
    source = str(source_path.expanduser()).replace("'", "'\\''")
    prefix = "\n".join(
        [
            "#!/bin/sh",
            "# Generated by job-utils setup.",
            "JOBUTILS_SOURCE='{}'".format(source),
            "JOBUTILS_PYTHON='{}'".format(quoted),
            'if [ -n "${PYTHONPATH:-}" ]; then',
            '  PYTHONPATH="$JOBUTILS_SOURCE:$PYTHONPATH"',
            "else",
            '  PYTHONPATH="$JOBUTILS_SOURCE"',
            "fi",
            "export PYTHONPATH",
        ]
    )
    if command == "jobutils":
        return prefix + "\nexec '{}' -m jobutils \"$@\"\n".format(quoted)
    if command == "jobutils-python":
        return prefix + "\nexec '{}' \"$@\"\n".format(quoted)
    configured_root = ""
    if gtd_repo is not None:
        configured = str(Path(gtd_repo).expanduser().resolve()).replace("'", "'\\''")
        configured_root = "JOBUTILS_CONFIGURED_GTD_ROOT='{}'\n".format(configured)
    return prefix + "\n" + configured_root + "\n".join(
        [
            "command -v vim >/dev/null 2>&1 || { echo 'jobutils-vim: Vim was not found' >&2; exit 127; }",
            'jobutils_gtd_root="${JOBUTILS_CONFIGURED_GTD_ROOT:-${GTD_ROOT:-}}"',
            'if [ -z "$jobutils_gtd_root" ] && [ -f "gtd.md" ]; then jobutils_gtd_root=$(pwd); fi',
            'if [ -n "$jobutils_gtd_root" ] && [ -f "$jobutils_gtd_root/gtd.md" ]; then',
            '  "$JOBUTILS_PYTHON" -m jobutils sync update --repo "$jobutils_gtd_root" || exit $?',
            'fi',
            'if [ "$#" -eq 0 ]; then',
            '  if [ -n "${JOBUTILS_CONFIGURED_GTD_ROOT:-}" ] && [ -f "$JOBUTILS_CONFIGURED_GTD_ROOT/gtd.md" ]; then',
            '    set -- "$JOBUTILS_CONFIGURED_GTD_ROOT/gtd.md"',
            '  elif [ -n "${GTD_ROOT:-}" ] && [ -f "$GTD_ROOT/gtd.md" ]; then',
            '    set -- "$GTD_ROOT/gtd.md"',
            '  elif [ -f "gtd.md" ]; then',
            '    set -- "gtd.md"',
            "  fi",
            "fi",
            'exec vim "$@"',
            "",
        ]
    )


def install_user_wrappers(
    job_utils_root: Path,
    user_bin: Path,
    platform_name: str,
    gtd_repo: Optional[Path] = None,
) -> Dict[str, Path]:
    """Install user-local command wrappers that bypass venv activation."""

    root = Path(job_utils_root).resolve()
    user_bin = Path(user_bin).expanduser()
    user_bin.mkdir(parents=True, exist_ok=True)
    if platform_name == "windows":
        python_path = root / ".venv" / "Scripts" / "python.exe"
        source_path = str(root / "src").replace("/", "\\")
        configured_root = (
            str(Path(gtd_repo).expanduser().resolve()).replace("/", "\\")
            if gtd_repo is not None
            else ""
        )
        configured_line = (
            'set "JOBUTILS_CONFIGURED_GTD_ROOT={}"\r\n'.format(configured_root)
            if configured_root
            else ""
        )
        specs = {
            "jobutils": '@echo off\r\n@rem Generated by job-utils setup.\r\nset "PYTHONPATH={};%PYTHONPATH%"\r\n"{}" -m jobutils %*\r\n'.format(source_path, python_path),
            "jobutils-python": '@echo off\r\n@rem Generated by job-utils setup.\r\nset "PYTHONPATH={};%PYTHONPATH%"\r\n"{}" %*\r\n'.format(source_path, python_path),
            "jobutils-vim": '@echo off\r\n@rem Generated by job-utils setup.\r\nset "PYTHONPATH={};%PYTHONPATH%"\r\n{}where vim >nul 2>nul || (echo jobutils-vim: Vim was not found 1>&2 & exit /b 127)\r\nset "JOBUTILS_REPO="\r\nif defined JOBUTILS_CONFIGURED_GTD_ROOT if exist "%JOBUTILS_CONFIGURED_GTD_ROOT%\\gtd.md" set "JOBUTILS_REPO=%JOBUTILS_CONFIGURED_GTD_ROOT%"\r\nif not defined JOBUTILS_REPO if defined GTD_ROOT if exist "%GTD_ROOT%\\gtd.md" set "JOBUTILS_REPO=%GTD_ROOT%"\r\nif not defined JOBUTILS_REPO if exist "gtd.md" set "JOBUTILS_REPO=%CD%"\r\nif defined JOBUTILS_REPO "{}" -m jobutils sync update --repo "%JOBUTILS_REPO%" || exit /b %ERRORLEVEL%\r\nif "%~1"=="" (\r\n  if defined JOBUTILS_REPO set "JOBUTILS_GTD=%JOBUTILS_REPO%\\gtd.md"\r\n)\r\nif defined JOBUTILS_GTD (vim "%JOBUTILS_GTD%") else (vim %*)\r\n'.format(source_path, configured_line, python_path),
        }
        paths = {}
        for name, content in specs.items():
            path = user_bin / (name + ".cmd")
            _write_managed_file(path, content, "Generated by job-utils setup.")
            paths[name] = path
        return paths
    python_path = root / ".venv" / "bin" / "python"
    paths = {}
    for name in ("jobutils", "jobutils-python", "jobutils-vim"):
        path = user_bin / name
        content = _posix_wrapper(python_path, root / "src", name, gtd_repo)
        _write_managed_file(path, content, "# Generated by job-utils setup.")
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        paths[name] = path
    return paths


def ensure_shell_profile(
    profile_path: Path,
    user_bin: Path,
    platform_name: str,
    job_utils_root: Optional[Path] = None,
) -> Path:
    """Add the user-local PATH and optional activation helper once."""

    profile_path = Path(profile_path).expanduser()
    user_bin = Path(user_bin).expanduser().resolve()
    root = Path(job_utils_root).expanduser().resolve() if job_utils_root else None
    if platform_name == "windows":
        if root is None:
            raise SetupError("job-utils root is required for the Windows activation helper")
        activation_root = str(root / ".venv").replace("/", "\\")
        block = "\n".join(
            [
                BEGIN_MARKER,
                '$env:Path = "{};" + $env:Path'.format(str(user_bin).replace('"', '""')),
                "function jobutils-activate {{ & '{}\\Scripts\\Activate.ps1' }}".format(
                    activation_root.replace("'", "''")
                ),
                END_MARKER,
            ]
        )
    else:
        venv_root = (root / ".venv") if root else (user_bin.parent.parent / ".venv")
        block = "\n".join(
            [
                BEGIN_MARKER,
                'export PATH="{}:$PATH"'.format(str(user_bin).replace('"', '\\"')),
                "jobutils-activate() {{ . '{}'; }}".format(
                    str(venv_root / "bin" / "activate").replace("'", "'\\''")
                ),
                END_MARKER,
            ]
        )
    existing = profile_path.read_text(encoding="utf-8") if profile_path.is_file() else ""
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    updated = _replace_managed_block(existing, block)
    if updated != existing:
        profile_path.write_text(updated, encoding="utf-8")
    return profile_path


def _write_json(path: Path, value: Dict) -> None:
    """Write setup state atomically without credentials."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(str(temporary), str(path))


def _record_step(state_path: Path, step: str, status: str, error: Optional[str] = None) -> None:
    """Record one safe setup step."""

    occurred_at = datetime.utcnow().isoformat() + "Z"
    current = {}
    if state_path.is_file():
        try:
            current = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            current = {}
    current.setdefault("steps", {})[step] = {
        "status": status,
        "at": occurred_at,
    }
    if error:
        current["steps"][step]["error"] = error
    _write_json(state_path, current)
    log_path = state_path.with_name("setup.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {"at": occurred_at, "step": step, "status": status}
    if error:
        record["error"] = error
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _run_setup_step(state_path: Path, step: str, action: Callable[[], object]) -> object:
    """Run one setup action and record completion or a safe failure."""

    try:
        result = action()
    except (OSError, SetupError, ValueError) as error:
        _record_step(state_path, step, "failed", str(error))
        raise
    _record_step(state_path, step, "completed")
    return result


def _home_directory() -> Path:
    """Resolve the user home while allowing isolated setup tests."""

    if os.name == "nt":
        return Path(os.environ.get("USERPROFILE", str(Path.home())))
    return Path(os.environ.get("HOME", str(Path.home())))


def run_setup(
    job_utils_root: Path,
    gtd_repo: Path,
    platform_name: Optional[str] = None,
    skip_env_prompt: bool = False,
    home: Optional[Path] = None,
    input_fn: Callable[[str], str] = input,
    secret_input_fn: Callable[[str], str] = getpass.getpass,
) -> Dict:
    """Run all non-destructive setup steps and return safe status data."""

    root = Path(job_utils_root).expanduser().resolve()
    platform_name = platform_name or detect_platform()
    if platform_name not in SUPPORTED_PLATFORMS:
        raise SetupError("unsupported setup platform: {}".format(platform_name))
    if shutil.which("vim") is None:
        raise SetupError("Vim was not found; install Vim before running setup")
    target = validate_gtd_repository(gtd_repo)
    home = Path(home or _home_directory()).expanduser().resolve()
    paths = SetupPaths(root, target, platform_name, home)
    state_path = paths.state_root / "state.json"
    steps = {}
    status_before_setup = _git_worktree_status(target)
    _run_setup_step(state_path, "repository", lambda: None)
    steps["repository"] = "completed"
    _run_setup_step(state_path, "gtd_repository", lambda: bootstrap_gtd_repository(target))
    steps["gtd_repository"] = "completed"
    setup_commit = _run_setup_step(
        state_path,
        "gtd_setup_commit",
        lambda: ensure_gtd_setup_commit(target, status_before_setup),
    )
    steps["gtd_setup_commit"] = (
        setup_commit.get("status", "completed")
        if isinstance(setup_commit, dict)
        else "completed"
    )
    if not skip_env_prompt:
        _run_setup_step(
            state_path,
            "env",
            lambda: ensure_env_file(
                root, input_fn=input_fn, secret_input_fn=secret_input_fn
            ),
        )
        steps["env"] = "completed"
    else:
        _record_step(state_path, "env", "skipped")
        steps["env"] = "skipped"
    user_bin = paths.user_bin
    wrapper_platform = "windows" if platform_name == "windows" else "posix"
    _run_setup_step(
        state_path,
        "wrappers",
        lambda: install_user_wrappers(root, user_bin, wrapper_platform, target),
    )
    steps["wrappers"] = "completed"
    if platform_name == "windows":
        vimrc = home / "_vimrc"
        snippet = home / "vimfiles" / "jobutils.vim"
        profiles = (
            home / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1",
            home
            / "Documents"
            / "WindowsPowerShell"
            / "Microsoft.PowerShell_profile.ps1",
        )
        python_command = user_bin / "jobutils-python.cmd"
    else:
        vimrc = home / ".vimrc"
        snippet = home / ".vim" / "jobutils.vim"
        shell = os.environ.get("SHELL", "")
        profiles = (home / (".zshrc" if shell.endswith("zsh") else ".bashrc"),)
        python_command = user_bin / "jobutils-python"
    _run_setup_step(
        state_path,
        "vim_and_profile",
        lambda: (
            ensure_vimrc_registration(vimrc, snippet, str(python_command), root),
            tuple(
                ensure_shell_profile(profile, user_bin, wrapper_platform, root)
                for profile in profiles
            ),
        ),
    )
    steps["vim_and_profile"] = "completed"
    return {
        "platform": platform_name,
        "job_utils_root": str(root),
        "gtd_repo": str(target),
        "venv": str(paths.venv_root),
        "user_bin": str(user_bin),
        "state": str(state_path),
        "steps": steps,
    }
