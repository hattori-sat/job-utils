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
source tree, and asks for the path to an existing local Git repository for the
GTD Markdown data. The directory must already exist and contain `.git`; an
empty repository with a README is valid. A missing path or a non-Git path stops
before any GTD file is created.

Setup is resumable. Existing files are never overwritten. Missing `gtd.md`,
`docs.md`, task/document directories, and metric directories are created in the
GTD Repository. Setup state and a redacted step log are stored under
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

Validate the non-secret destination profile with:

```text
jobutils config validate --path /absolute/path/to/config.yaml
```

## Commands available from anywhere

Setup writes wrappers to a user-local command directory and adds that directory
to the shell profile. Open a new terminal after setup, or source the profile
shown in the setup output.

- `jobutils` runs the Python CLI using this checkout's virtual environment.
- `jobutils-python` runs that same Python interpreter for manual work.
- `jobutils-vim` starts Vim with the configured environment.
- `jobutils-activate` is an optional helper for manual Python commands.

The wrappers use absolute paths, so the CLI and Vim do not depend on the
current directory or on a manually activated virtual environment.

## Vim integration

Setup writes a user-local Vim snippet containing the absolute job-utils runtime
path and virtual-environment Python path, then registers it in `.vimrc` on
macOS/Ubuntu or `_vimrc` on Windows. The registration is a managed block and is
updated without duplication. Restart Vim after setup.

The runtime enables Vim's standard filetype, syntax, and indent support for
Markdown, JSON, XML, C, C++, CMake, and Makefiles. Makefiles retain literal
tabs; Markdown and structured data use two-column indentation, while C-family
and CMake files use four-column indentation. See the
[Vim workflow research note](../research/vim-workflow-settings.md).

Markdown buffers use Vim's native list formatting. Press Enter after an
unordered (`-`, `*`, or `+`) list item to continue its marker. Numbered list
markers are recognized by Vim's native formatter for indentation and wrapping;
the number itself is not auto-incremented. The behavior is buffer-local and
does not change Makefile literal-tab handling.

`:Gtd` and `:GtdTask` have separate responsibilities. `:Gtd` only moves
prefixed lines between GTD sections; it does not create task Markdown. Use
`:GtdTask` on the selected line when that item needs a task document. The same
distinction is available in the CLI as `gtd dispatch` and `gtd task`.

Available commands include:

- `:Gtd` / `:gtd` — dispatch the GTD index;
- `:GtdTask` / `:gtdtask` — create or open the current task detail;
- `:GtdSubtask` / `:gtdsubtask` — create a child from a task's `# Subtasks` section;
- `:GtdDoc` / `:gtddoc` — create or open the current document detail;
- `:GtdTags` — show the standard tag catalog;
- `:GtdImpactLevels` — show impact levels;
- `:GtdReview` — show the current-year metrics summary;
- `:GtdMetricsHelp` — show metrics commands;
- `:GtdSyncPlan` — create a reviewable Jira/Confluence synchronization plan;
- `:GtdSyncApply [plan]` — apply the newest or named plan after confirmation;
- `:GtdSyncPull` — pull external changes after confirmation;
- `:GtdSyncStatus` — show local plans, bases, pending actions, and conflicts;
- `:GtdSyncHelp` — show synchronization commands;
- `:JobutilsProjectRoot` — show the nearest CMake project root.
- `:JobutilsCMake` — open the nearest `CMakeLists.txt` in a split.

For C, C++, and CMake projects, the project helpers use the nearest directory
containing `CMakeLists.txt`:

- `:JobutilsCMakeConfigure` — configure `<project>/build` with CMake;
- `:JobutilsCMakeBuild` — build the configured CMake tree;
- `:JobutilsCMakeTest` — run CTest with failure output;
- `:JobutilsMake` — run `make` from the project root;
- `:JobutilsClangFormat` — format the current C or C++ buffer with
  `clang-format`;
- `:JobutilsCompileCommands` — open `compile_commands.json` from the project
  root or its build directory;
- `:JobutilsQuickfix` — open the current Quickfix list.

Command output is placed in the Quickfix list. Use Vim's `:cnext`, `:cprev`,
and `:copen` to review build, test, or compiler messages. CMake, CTest,
Make, and clang-format must be available on `PATH` when their commands are
used.

Yocto and OpenEmbedded metadata uses the `bitbake` filetype for `.bb`,
`.bbappend`, `.bbclass`, recipe `.inc`, and `conf/*.conf` files. The local
runtime adds syntax highlighting, four-column indentation, `#` comments, and
file lookup suffixes for common metadata extensions. It does not run BitBake
automatically; use the project build tools or a project-specific command when
the build environment has been initialized.

The Vim runtime also enables `number`, `cursorline`, and `ruler` by default.
Set `g:jobutils_enable_defaults = 0` before loading the runtime when the
display defaults should remain unchanged.

## Basic CLI examples

```text
jobutils gtd dispatch --repo /absolute/path/to/your-gtd-repository
jobutils gtd task --repo /absolute/path/to/your-gtd-repository --line 12
jobutils gtd subtask --repo /absolute/path/to/your-gtd-repository \
  --parent gtd_tasks/<parent-task>.md --line 18
jobutils gtd document --repo /absolute/path/to/your-gtd-repository --line 8
jobutils metrics catalog --repo /absolute/path/to/your-gtd-repository
jobutils metrics report --repo /absolute/path/to/your-gtd-repository --from 2026-01-01 --to 2026-12-31
jobutils sync plan --repo /absolute/path/to/your-gtd-repository
jobutils sync status --repo /absolute/path/to/your-gtd-repository
```

Synchronization is deliberately a two-step workflow. `sync plan` reads
publishable Markdown and writes a JSON plan under
`.jobutils/sync/plans/`. Review that file, then use `:GtdSyncApply` or
`jobutils sync apply --plan PATH --adapter atlassian`. The Vim command uses
the newest plan when no path is supplied and asks for confirmation before it
writes to Jira or Confluence. `:GtdSyncPull` also asks for confirmation before
writing pulled changes into local Markdown.

Generated reports are placed under `.jobutils/output/<generation-date>/<period>/`
and are ignored by Git. Metric event JSONL remains source data and should be
committed with the GTD Repository.

To create a child task, open the parent task Markdown, add a bullet under
`# Subtasks`, and run `:GtdSubtask` on that bullet. The current file is used as
the parent automatically; the child is stored below the parent's directory.
