# Setup

job-utils expects Python and Vim to be available on the host. It does not
install either one, and it does not install AI skills.

## Install the Python package

From this repository:

```text
python -m pip install --editable .
```

Use `python3` on systems where `python` names another interpreter. The package
uses the Python standard library and supports Python 3.8 or newer.

For development formatting, install the pinned development tool and run:

```text
python -m pip install -r requirements-dev.txt
python -m black src tests
python -m black --check src tests
```

## Enable the Vim commands

Add the repository's Vim directory to Vim's runtime path and select the Python
executable used by the wrapper:

```vim
set runtimepath^=/absolute/path/to/job-utils/vim
let g:jobutils_python = 'python3'
```

On Windows, use a Windows path and set `g:jobutils_python` to `python` or the
absolute path to the intended interpreter.

The commands are:

- `:Gtd` / `:gtd` — dispatch the GTD index;
- `:GtdTask` / `:gtdtask` — create or open the current task detail;
- `:GtdTags` — show the standard tag catalog;
- `:GtdImpactLevels` — show impact levels;
- `:GtdReview` — show the current-year metrics summary;
- `:GtdMetricsHelp` — show the metrics commands.

The commands locate `gtd.md` in the current directory or an ancestor and work
with the separate GTD Markdown Repository.

## CLI examples

```text
python -m jobutils gtd dispatch --repo /path/to/gtd-repository
python -m jobutils metrics catalog --repo /path/to/gtd-repository
python -m jobutils metrics report --repo /path/to/gtd-repository --from 2026-01-01 --to 2026-12-31
python -m jobutils sync plan --repo /path/to/gtd-repository
```

Generated reports are placed under `.jobutils/output/<generation-date>/<period>/`
and are ignored by Git. Metric event JSONL remains source data and should be
committed with the GTD Repository.
