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
- `:GtdSubdocument` / `:gtdsubdocument` — create a recursive child from a document's `# Subdocuments` section;
- `:GtdTaskHelp` / `:gtdtaskhelp` — show task fields, prefixes, tags, and Jira inputs;
- `:GtdDocHelp` / `:gtddochelp` — show document fields, Confluence inputs, and parent relationships;
- `:GtdTags` — show the standard tag catalog;
- `:GtdImpactLevels` — show impact levels;
- `:GtdReview` — show the current-year metrics summary;
- `:GtdStart` / `:gtdstart` — record the start of an explicit work interval for the current task;
- `:GtdStop` / `:gtdstop` — record the end of an explicit work interval for the current task;
- `:GtdMetricsHelp` — show metrics commands;
- `:GtdSyncPlan` — create a reviewable Jira/Confluence synchronization plan;
- `:GtdSyncApply [plan]` — apply the newest or named plan, commit local sync state, and push after confirmation;
- `:GtdSyncPull` — pull external changes after confirmation;
- `:GtdSyncStatus` — show local plans, bases, pending actions, and conflicts;
- `:GtdSyncRebind [path]` — update a stored Jira/Confluence identity locally;
- `:GtdSyncCheck` — inspect external drift without changing files;
- `:GtdGitPush [remote] [branch]` — push an already committed GTD repository branch after confirmation;
- `:GtdSyncHelp` — show synchronization commands;
- `:GtdFormat` / `:gtdformat` — normalize a saved Markdown buffer while preserving fenced code and front matter;
- `:PasteImage [alt text]` / `:pasteimage` — save a clipboard PNG under `assets/` and insert its Markdown link;
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
jobutils gtd subdocument --repo /absolute/path/to/your-gtd-repository \
  --parent documents/<parent>.md --line 14
jobutils metrics catalog --repo /absolute/path/to/your-gtd-repository
jobutils metrics report --repo /absolute/path/to/your-gtd-repository --from 2026-01-01 --to 2026-12-31 --format html,csv,svg,json
jobutils markdown paste-image --repo /absolute/path/to/your-gtd-repository --file documents/guide.md --name diagram
jobutils markdown format --path /absolute/path/to/your-gtd-repository/documents/guide.md
jobutils markdown format --path /absolute/path/to/your-gtd-repository/documents/guide.md --check
jobutils sync plan --repo /absolute/path/to/your-gtd-repository
jobutils sync status --repo /absolute/path/to/your-gtd-repository
jobutils git status --repo /absolute/path/to/your-gtd-repository
jobutils git commit --repo /absolute/path/to/your-gtd-repository --message "chore: save local GTD changes"
jobutils git push --repo /absolute/path/to/your-gtd-repository --remote origin
jobutils git push-mock --repo /absolute/path/to/your-gtd-repository
```

When state-based time is too broad, record a focused work interval explicitly:

```bash
jobutils metrics start --repo /absolute/path/to/your-gtd-repository --gtd-id TASK-UUID
jobutils metrics stop --repo /absolute/path/to/your-gtd-repository --gtd-id TASK-UUID
```

Reports use explicit work intervals for active time when they exist for a task;
otherwise they use the GTD state transitions.

Synchronization has an explicit review step followed by one confirmed apply.
`sync plan` reads publishable Markdown and writes a JSON plan under
`.jobutils/sync/plans/`. Review that file, then use `:GtdSyncApply` or
`jobutils sync apply --plan PATH --adapter atlassian`. The apply operation uses
the newest plan when no path is supplied, asks for confirmation before writing
to Jira or Confluence, commits the resulting local synchronization metadata,
and pushes the commit to the configured Git remote. If push fails, rerun
`jobutils git push` after resolving the remote problem. `:GtdSyncPull` asks for
confirmation before writing pulled changes into local Markdown; commit and
push those pulled changes with the Git commands above.

Use `jobutils sync check --repo /absolute/path/to/your-gtd-repository
--adapter atlassian` or `:GtdSyncCheck` before planning when you want to see
whether Jira or Confluence changed outside the Markdown workflow. The check is
read-only. It reports clean, local-only, external-only, converged, conflict,
unknown, and per-item error states; use `:GtdSyncPull` only after reviewing
those results.

If an external Jira issue key or Confluence page ID changes, use the local
rebind command before creating a new plan:

```text
jobutils sync rebind --repo /absolute/path/to/your-gtd-repository \
  --path documents/guide.md --kind confluence --external-id 12345 \
  --url https://example.invalid/wiki/pages/12345 --parent-id 67890
```

Rebind updates front matter only; it does not contact Jira or Confluence.
Afterward, run `sync plan` again and review the resulting actions.

Generated reports are placed under `.jobutils/output/<generation-date>/<period>/`
and are ignored by Git. Metric event JSONL remains source data and should be
committed with the GTD Repository.

## Paste a screenshot into Markdown

Copy a PNG screenshot to the system clipboard, open the target Markdown file
in Vim, and run `:PasteImage` or `:PasteImage diagram`. The image is saved
under `assets/` next to the current Markdown file, and a relative link such as
`![diagram](assets/guide-a1b2c3d4.png)` is inserted below the cursor. The
lowercase `:pasteimage` form is also available.

The Python equivalent is:

```text
jobutils markdown paste-image --file /absolute/path/to/guide.md --name diagram
```

Clipboard access uses the first available provider for the platform:

- macOS: `pngpaste`, then the built-in `osascript` fallback;
- Windows: `powershell` or `pwsh` with Windows Forms and Drawing;
- Linux: Wayland `wl-paste`, then X11 `xclip`.

Setup does not install clipboard tools automatically. If none is available,
the command reports the missing provider and the supported alternatives. The
paste command only creates a local image file and Markdown link; it does not
upload the image to Jira or Confluence and does not run Git push.

To create a child task, open the parent task Markdown, add a bullet under
`# Subtasks`, and run `:GtdSubtask` on that bullet. The current file is used as
the parent automatically; the child is stored below the parent's directory.

To create a child document, open the parent document Markdown, add a bullet
under `# Subdocuments`, and run `:GtdSubdocument`. The child is stored below
the parent's directory. Its `parent_document_id`, `confluence_parent_path`,
and inherited publication fields are written at creation time. When a parent
has not yet received a Confluence page ID, `sync apply` creates the parent
first and passes its returned page ID to the child.

The Jira project, issue type, progress-comment field, Confluence space, and
default parent page are taken from `.env` when the corresponding Markdown
front-matter value is empty. Explicit front matter overrides those defaults.

## Published Markdown content

Published document Markdown is converted to Confluence storage content. The
supported subset includes headings, paragraphs, links, images, unordered and
ordered lists, pipe tables, fenced code blocks, and explicit macro directives.
Use a directive when a document needs a Confluence macro that has no ordinary
Markdown equivalent:

```markdown
:::confluence-macro name=info
This text is the macro body.
:::
```

Local links and images are replaced with published external URLs when their
target has a stored external identity. A private local target is omitted from
the external payload. Jira task descriptions use the same Markdown blocks for
structured ADF paragraphs, headings, links, lists, tables, and code blocks.
Pull converts the supported Confluence storage and Jira ADF subset back to
canonical Markdown.
