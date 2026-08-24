# Setup

job-utils is the utility repository. The GTD Markdown Repository is a separate
local Git working tree. Setup connects the two local directories; it does not
clone, create a remote, or push anything.

## First setup

Python 3.8 or newer and Vim must already be installed. The setup scripts do
not replace either installation and do not install AI skills.

On macOS or Ubuntu:

```text
./scripts/setup.sh
```

On Windows PowerShell:

```powershell
.\scripts\setup.ps1
```

The script creates or reuses `job-utils/.venv`, connects it to this checkout's
source tree, and asks for the path to an existing local Git repository
for the GTD Markdown data. The directory must already exist and contain
`.git`; an empty repository with a README is valid. A missing path or a
non-Git path stops before any GTD file is created.

Setup is resumable. Existing files are never overwritten. Missing `gtd.md`,
`docs.md`, task/document directories, and metric directories are created in
the GTD Repository. Setup state and a redacted step log are stored under
`.jobutils/setup/` in the job-utils checkout and are ignored by Git.

If setup is interrupted, run the same platform script again. It reuses the
virtual environment and fills only missing configuration or registration.

## Configuration

The script creates or completes `.env` in the job-utils checkout. Non-secret
values are entered normally; Jira and Confluence tokens are requested with
hidden input. Existing values are preserved. The file is ignored by Git and
must never be copied into the Markdown Repository.

See [environment variables](environment-variables.md) for the meaning of each
setting. The lower-level operation is:

```text
jobutils setup init --gtd-repo /absolute/path/to/your-gtd-repository
```

The non-secret destination profile can be checked with:

```text
jobutils config validate --path /absolute/path/to/config.yaml
```

## Commands available from anywhere

Setup writes wrappers to a user-local command directory and adds that
directory to the shell profile. Open a new terminal after setup, or source the
profile shown in the setup output.

- `jobutils` runs the Python CLI using this checkout's virtual environment.
- `jobutils-python` runs that same Python interpreter for manual work.
- `jobutils-vim` starts Vim with the configured environment.
- `jobutils-activate` is an optional helper for manual Python commands;
  normal `jobutils` use does not require activation.

The wrappers use absolute paths, so the CLI and Vim do not depend on the
current directory or on a manually activated virtual environment.

## Vim integration

Setup writes a user-local Vim snippet containing the absolute job-utils runtime
path and virtual-environment Python path, then registers it in `.vimrc` on
macOS/Ubuntu or `_vimrc` on Windows. The registration is a managed block and
is updated without duplication. Restart Vim after setup.

The existing Vim configuration remains yours. The current runtime provides:

The runtime enables Vim's standard filetype, syntax, and indent support for
Markdown, JSON, XML, C, C++, CMake, and Makefiles. Makefiles retain literal
tabs; Markdown and structured data use two-column indentation, while C-family
and CMake files use four-column indentation. See the
[Vim workflow research note](../research/vim-workflow-settings.md) for the
reasoning and disable switches.

- `:Gtd` / `:gtd` — dispatch the GTD index;
- `:GtdTask` / `:gtdtask` — create or open the current task detail;
- `:GtdDoc` / `:gtddoc` — create or open the current document detail;
- `:GtdTags` — show the standard tag catalog;
- `:GtdImpactLevels` — show impact levels;
- `:GtdReview` — show the current-year metrics summary;
- `:GtdMetricsHelp` — show metrics commands.

## Basic CLI examples

```text
jobutils gtd dispatch --repo /absolute/path/to/your-gtd-repository
jobutils metrics catalog --repo /absolute/path/to/your-gtd-repository
jobutils metrics report --repo /absolute/path/to/your-gtd-repository --from 2026-01-01 --to 2026-12-31
jobutils sync plan --repo /absolute/path/to/your-gtd-repository
```

Generated reports are placed under `.jobutils/output/<generation-date>/<period>/`
and are ignored by Git. Metric event JSONL remains source data and should be
committed with the GTD Repository.
