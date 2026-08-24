# Platform Notes

## macOS and Ubuntu

Use the shared POSIX entry point from the job-utils checkout:

```text
./scripts/setup.sh
```

The script distinguishes macOS from Ubuntu, rejects other Linux distributions,
uses an already-installed Python 3.8+ interpreter, and creates or reuses
`.venv`. It does not require that `python` be globally selected. The generated
wrappers call the virtual-environment interpreter directly.

The command directory is `~/.local/bin`. Setup adds it to `.zshrc` for zsh or
`.bashrc` for another POSIX shell. A new terminal is normally enough to load
the path; `jobutils-activate` is available only when manual activation is
useful.

## Windows

Use the PowerShell entry point:

```powershell
.\scripts\setup.ps1
```

It prefers `JOBUTILS_PYTHON`, then `py -3`, then `python`, checks Python 3.8+
and creates or reuses `.venv\Scripts`. User wrappers are placed in
`%USERPROFILE%\bin` and the PowerShell profile is updated. Vim uses `_vimrc`
and a local `vimfiles\jobutils.vim` snippet.

PowerShell execution policy and Vim installation are host policy. If either
prevents setup, the script stops with the failing prerequisite rather than
silently writing a partial registration.

## Local repository requirement

The GTD data path is a local, existing, non-bare Git working tree. Setup never
uses a URL, creates a remote, clones, pushes, or overwrites an existing user
file. This is intentional: Git synchronization of the Markdown repository is
kept separate from installation of the job-utils tools.

## Compatibility

The runtime avoids third-party dependencies and newer Python syntax. Vim
integration uses long-standing features such as `system()`, `findfile()`,
`shellescape()`, and user commands. Live Jira/Confluence access depends on the
account permissions and API configuration of the installation.
