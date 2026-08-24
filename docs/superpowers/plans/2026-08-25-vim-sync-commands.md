# Vim Sync Commands Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide a safe Vim entry point for reviewing synchronization plans, applying the selected plan to Jira/Confluence, pulling external changes, and inspecting local synchronization state.

**Architecture:** Keep synchronization decisions in the existing Python engine. Add a read-only `sync status` CLI operation, then wrap `sync plan`, `sync apply`, `sync pull`, and `sync status` in the classic Vim GTD plugin. Apply and pull remain confirmation-gated; apply uses the most recent saved plan unless a plan path is supplied.

**Tech Stack:** Python standard library, argparse, JSON state files, classic Vimscript, unittest.

**Spec:** `spec/sync/plan-apply.md`

## Global Constraints

- Markdown in the separate GTD Repository is the canonical local representation.
- Plan generation does not call an external write endpoint.
- `sync apply` verifies the source hash before executing actions.
- Implementation Notes are removed before Jira or Confluence payloads are created.
- Authentication material is read from environment variables and never written to plan or state files.
- Work on a `codex/*` branch and do not merge into `main`.

---

### Task 1: Add synchronization status to the Python CLI

**Files:**
- Modify: `src/jobutils/sync/engine.py`
- Modify: `src/jobutils/cli.py`
- Test: `tests/test_sync.py`

**Interfaces:**
- Produces `sync_status(repo_root: Path) -> Dict[str, object]` with `plan_count`, `latest_plan`, `base_count`, `pending_actions`, and `conflict_count`.
- Produces `jobutils sync status --repo PATH`, printing one JSON object and never contacting Jira or Confluence.

- [x] **Step 1: Write the failing test**

Create a repository with one saved plan, one base snapshot, and a Markdown conflict marker. Assert that `sync_status()` reports those counts and that the CLI emits the same JSON.

- [x] **Step 2: Run the focused test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest tests.test_sync.SyncTests.test_sync_status_reports_local_state -v`

Expected: FAIL because the status function and CLI operation do not exist.

- [x] **Step 3: Implement the minimal status boundary**

Read only `.jobutils/sync/plans/*.json`, `.jobutils/sync/bases/*.md`, and managed Markdown files. Use the newest plan for `pending_actions`; return `latest_plan` relative to the GTD Repository. Do not instantiate an external adapter.

- [x] **Step 4: Run the focused test to verify it passes**

Run the focused unittest command again and confirm it passes.

- [x] **Step 5: Commit**

```bash
git add src/jobutils/sync/engine.py src/jobutils/cli.py tests/test_sync.py
git commit -m "feat: add local sync status"
```

### Task 2: Add Vim synchronization commands

**Files:**
- Modify: `vim/plugin/jobutils_gtd.vim`
- Modify: `vim/autoload/jobutils/gtd.vim`
- Modify: `docs/setup/README.md`
- Test: `tests/test_vim_runtime.py`

**Interfaces:**
- Adds `:GtdSyncPlan`, `:GtdSyncApply [plan]`, `:GtdSyncPull`, `:GtdSyncStatus`, and `:GtdSyncHelp`.
- Adds lowercase command-line aliases `gtdsyncplan`, `gtdsyncapply`, `gtdsyncpull`, `gtdsyncstatus`, and `gtdsynchelp`.
- `:GtdSyncApply` selects the newest `.jobutils/sync/plans/*.json` when no argument is provided and asks for `A`pply or `C`ancel before invoking `sync apply --adapter atlassian`.
- `:GtdSyncPull` asks for confirmation before invoking `sync pull --adapter atlassian`.
- Errors are shown through Vim's error message area; successful output is retained in `:messages`.

- [x] **Step 1: Write the failing tests**

Extend the Vim runtime test to assert command registration and lowercase aliases. Add a noninteractive cancellation case by setting `g:jobutils_sync_confirm` to `C`, then assert that no Python sync command is invoked.

- [x] **Step 2: Run the focused tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest tests.test_vim_runtime.VimRuntimeTests.test_sync_commands_are_available_with_lowercase_aliases -v`

Expected: FAIL because the commands are not registered.

- [x] **Step 3: Implement the Vim wrappers**

Reuse the existing repository-root and Python-wrapper helpers. Add a plan-path resolver based on `.jobutils/sync/plans/*.json`, a confirmation helper that accepts only `A`/`C` and `Y`/`N` as appropriate, and output/error helpers that do not expose credentials.

- [x] **Step 4: Run the focused tests to verify they pass**

Run the focused Vim unittest and confirm command registration and cancellation behavior.

- [x] **Step 5: Update the setup guide**

Document the five commands, the explicit confirmation behavior, the newest-plan default, and the CLI equivalents without including real project identifiers or credentials.

- [x] **Step 6: Commit**

```bash
git add vim/plugin/jobutils_gtd.vim vim/autoload/jobutils/gtd.vim tests/test_vim_runtime.py docs/setup/README.md
git commit -m "feat: add Vim synchronization workflow"
```

### Task 3: Verify the complete synchronization entry point

**Files:**
- Modify: `docs/superpowers/plans/2026-08-25-vim-sync-commands.md`

- [x] **Step 1: Run focused synchronization and Vim tests**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest tests.test_sync tests.test_vim_runtime -v`

- [x] **Step 2: Run the full suite and hygiene checks**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v` and `git diff --check`.

- [x] **Step 3: Review the public diff**

Confirm that no `.env`, `config.yaml`, private GTD repository data, Atlassian URLs, tokens, or generated output are staged.

- [x] **Step 4: Mark completed steps and commit the plan update**

Verified on 2026-08-25: the full suite completed with 67 passing tests and `git diff --check` was clean. The public diff contains no credentials, local configuration, private GTD data, or generated output.

## Self-review checklist

- The status command is local-only and does not instantiate an HTTP adapter.
- Apply and pull are explicit, confirmation-gated actions.
- Apply defaults to the latest reviewable plan but accepts an explicit plan path.
- Implementation Notes and credentials remain governed by the existing Python sync engine.
- Existing GTD dispatch and document creation commands remain unchanged.
