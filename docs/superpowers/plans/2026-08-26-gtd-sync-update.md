# GtdSyncUpdate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep the separate GTD Markdown Repository current from GitHub before Vim work begins, and prevent Jira/Confluence synchronization from operating on a stale Git branch.

**Architecture:** Add a safe, fast-forward-only `sync update` operation backed by the existing Git helper. The Vim launcher runs it before opening the repository, while `:GtdSyncUpdate` provides manual recovery. `sync check` and `sync apply` inspect the fetched Git state; apply also revalidates external content before writing.

**Tech Stack:** Python 3.8+ standard library, classic Vimscript, POSIX shell, Windows batch/PowerShell wrappers, unittest.

**Spec:** `spec/git/local-operations.md`, `spec/sync/check.md`, `spec/sync/plan-apply.md`, `spec/user-workflow.md`

## Global Constraints

- Markdown in the separate GTD Repository remains the local source of truth.
- Normal synchronization is `check` → `plan` → `apply`.
- Git operations must never force-push and must reject unsafe credential-shaped files before commit.
- Automatic startup update is fast-forward-only; divergent history must stop for explicit recovery.
- Jira and Confluence writes require a current observation and a current Git state.
- Implementation Notes and credentials are never published or stored in plans.
- Keep the Vim-centered workflow and Python 3.8+ compatibility.

---

### Task 1: Define Git synchronization states and the update CLI

**Files:**
- Modify: `src/jobutils/gitops.py`
- Modify: `src/jobutils/cli.py`
- Test: `tests/test_gitops.py`
- Test: `tests/test_sync.py`

**Interfaces:**
- `gitops.fetch()` returns `local_revision` and a state of `in_sync`, `remote_ahead`, `local_ahead`, or `diverged` when the remote branch is available.
- `jobutils sync update --repo REPO [--remote REMOTE] [--branch BRANCH]` performs the existing fast-forward-only pull and prints JSON.

- [x] **Step 1: Write failing tests** for `sync update`, remote-ahead detection, and divergent history.
- [x] **Step 2: Run the focused tests** and confirm the new command/state assertions fail.
- [x] **Step 3: Implement the minimal Git state calculation** using Git subprocesses without a shell; preserve current fetch/pull safety checks.
- [x] **Step 4: Add the `sync update` parser and handler** using the existing `pull()` helper; return a nonzero status with a readable recovery error when the worktree is dirty or history is not fast-forwardable.
- [x] **Step 5: Run the focused Git and CLI tests** and confirm they pass.
- [x] **Step 6: Commit:** `feat: add safe sync update operation`.

### Task 2: Block stale Git observations and revalidate external state

**Files:**
- Modify: `src/jobutils/sync/engine.py`
- Modify: `src/jobutils/cli.py`
- Modify: `tests/test_sync.py`

**Interfaces:**
- `sync check` records Git state in its observation and reports a blocked state when the remote branch is ahead or diverged.
- `create_plan()` rejects observations with an unresolved Git state.
- `sync apply` performs a final Git fetch before external writes when Git synchronization is enabled.
- `apply_plan()` re-fetches each existing external record represented by the observation and rejects a plan whose external body changed after check.

- [x] **Step 1: Write failing tests** for plan rejection after remote Git advancement, apply rejection before external mutation when Git is stale, and apply rejection when Jira/Confluence changes after check.
- [x] **Step 2: Run the focused tests** and confirm they fail.
- [x] **Step 3: Implement observation Git-state recording and plan blocking** while preserving offline/memory test behavior when no Git remote is configured.
- [x] **Step 4: Implement apply preflight checks** so stale Git or external state stops before any external write.
- [x] **Step 5: Run the focused synchronization tests** and confirm they pass.
- [x] **Step 6: Commit:** `fix: reject stale synchronization inputs`.

### Task 3: Add automatic startup update and manual Vim recovery

**Files:**
- Modify: `scripts/jobutils-vim`
- Modify: `scripts/jobutils-vim.ps1`
- Modify: `src/jobutils/setup_workflow.py`
- Modify: `vim/plugin/jobutils_gtd.vim`
- Modify: `vim/autoload/jobutils/gtd.vim`
- Modify: `tests/test_setup_profiles.py`
- Modify: `tests/test_setup_scripts.py`
- Modify: `tests/test_vim_runtime.py`

**Interfaces:**
- `jobutils-vim` and generated platform wrappers run `jobutils sync update` for the configured GTD Repository before opening Vim.
- `:GtdSyncUpdate` and `:gtdsyncupdate` perform the same fast-forward-only operation for manual recovery and reload the current buffer after success.
- Dirty worktrees and divergent history stop with an actionable error; no Jira/Confluence request is made.

- [x] **Step 1: Write failing wrapper and Vim runtime tests** for startup update, command registration, lowercase alias, success reload, and failure display.
- [x] **Step 2: Run the focused wrapper/Vim tests** and confirm they fail.
- [x] **Step 3: Implement startup update** in the checked-in POSIX/PowerShell wrappers and generated setup wrappers using the job-utils virtual-environment Python.
- [x] **Step 4: Implement `GtdSyncUpdate`** with confirmation-free local Git behavior, modified-buffer protection, output/error reporting, and buffer refresh.
- [x] **Step 5: Run the focused wrapper/Vim tests** and confirm they pass.
- [x] **Step 6: Commit:** `feat: update GTD repository before Vim sync`.

### Task 4: Document and verify the complete workflow

**Files:**
- Modify: `docs/setup/README.md`
- Modify: `docs/usage/README.md`
- Modify: `spec/git/local-operations.md`
- Modify: `spec/sync/check.md`
- Modify: `spec/sync/plan-apply.md`
- Modify: `spec/user-workflow.md`
- Modify: `vim/autoload/jobutils/gtd.vim`
- Modify: `vim/plugin/jobutils_gtd.vim`
- Test: `tests/test_setup_docs.py`

- [x] **Step 1: Update the user-facing workflow** to distinguish automatic startup update, manual `GtdSyncUpdate`, read-only check, and apply-owned commit/push.
- [x] **Step 2: Add `GtdSyncUpdate` to synchronization help** and remove any wording that implies check performs pull.
- [x] **Step 3: Sanitize the documentation** for standalone readers; exclude conversation residue, real project identifiers, credentials, and private paths.
- [x] **Step 4: Run the documentation tests, full test suite, shell syntax checks, Python compilation with a temporary cache, and `git diff --check`.
- [x] **Step 5: Scan the public diff for secrets, personal paths, and unrelated files.
- [x] **Step 6: Commit:** `docs: document startup Git synchronization`.

## Self-review checklist

- `sync update` is the only new normal user-facing Git operation; push remains owned by apply.
- Startup update never performs Jira or Confluence requests.
- `sync check` does not mutate the worktree, avoiding Vim buffer reload warnings.
- A stale Git or external observation blocks before external writes.
- Existing offline memory-adapter and direct engine tests remain valid.
