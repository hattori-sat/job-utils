# Synchronization Refresh and Plan/Apply Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make synchronization follow a Terraform-like check → plan → apply workflow with one post-apply commit and push, removing the user-facing `sync pull` path.

**Architecture:** `sync check` refreshes Git remote metadata and current Jira/Confluence records into ignored local observations. `sync plan` compares Markdown, the last synchronized base, and those observations, producing publish or import/conflict actions. `sync apply` executes the approved actions, updates Markdown and synchronization state, then commits once and pushes once.

**Tech Stack:** Python 3.8+, classic Vimscript, Git subprocesses without a shell, JSON observation/plan files, existing Jira/Confluence adapters, unittest.

**Spec:** `spec/sync/plan-apply.md`, `spec/sync/check.md`, `docs/research/plan-apply-design.md`

## Global Constraints

- The GTD Markdown Repository remains separate from job-utils.
- Markdown is the canonical local representation; Implementation Notes are never published.
- Jira and Confluence credentials remain in the environment and never enter plans, observations, logs, or commits.
- `sync check` does not commit or push.
- `sync plan` does not write to Jira or Confluence.
- `sync apply` commits after all local/external actions complete, then pushes the clean worktree.
- Work on the existing `codex/fix-vim-auto-open` branch and update PR #13; never push `main` directly.

---

### Task 1: Add Git remote refresh without merge

**Files:**
- Modify: `src/jobutils/gitops.py`
- Test: `tests/test_gitops.py`

**Interfaces:**
- Produces `fetch(repo_root: Path, remote: str = "origin") -> Dict[str, object]`.
- Runs `git fetch --prune <remote>` only; it never changes the working tree or merges a branch.

- [ ] **Step 1: Write the failing test** for a remote commit becoming visible after `fetch`, while the local branch and worktree remain unchanged.
- [ ] **Step 2: Run the focused Git tests and confirm failure.**
- [ ] **Step 3: Implement `gitops.fetch` with argument validation, credential redaction, and remote revision reporting.**
- [ ] **Step 4: Run the focused Git tests and confirm success.**
- [ ] **Step 5: Commit the Git refresh slice.**

### Task 2: Make `sync check` the explicit refresh boundary

**Files:**
- Modify: `src/jobutils/sync/engine.py`
- Modify: `src/jobutils/cli.py`
- Modify: `.gitignore`
- Modify: `spec/sync/check.md`
- Test: `tests/test_sync.py`

**Interfaces:**
- `check(repo_root: Path, adapter: SyncAdapter, refresh_git: bool = True) -> Dict[str, object]`.
- Writes the latest external records and drift classification to ignored `.jobutils/sync/observations/latest.json`.
- Returns Git refresh status, observation ID, and per-item drift states.

- [ ] **Step 1: Write failing tests** that require Git refresh status, an observation file, and external fetch results while preserving Markdown/base files.
- [ ] **Step 2: Run the focused sync tests and confirm failure.**
- [ ] **Step 3: Implement observation persistence and invoke the new Git fetch boundary.**
- [ ] **Step 4: Update the check contract to state that refresh metadata is local ignored state; check still never commits, pushes, or changes Markdown/Atlassian.**
- [ ] **Step 5: Run focused tests and commit the refresh/check slice.**

### Task 3: Generate plans from refreshed observations

**Files:**
- Modify: `src/jobutils/sync/engine.py`
- Modify: `src/jobutils/cli.py`
- Modify: `spec/sync/plan-apply.md`
- Modify: `docs/design/sync-plan-apply.md`
- Test: `tests/test_sync.py`

**Interfaces:**
- `create_plan(repo_root: Path, observations: Optional[Dict] = None) -> Dict`.
- Plan actions may be `create`, `update`, `import`, or `conflict`.
- Plans record the observation ID and reject apply when the observation no longer matches.

- [ ] **Step 1: Write failing tests** for external-only change → `import`, two-sided change → `conflict`, and unchanged state → no action.
- [ ] **Step 2: Run the focused tests and confirm failure.**
- [ ] **Step 3: Add observation loading and plan action generation without embedding credentials or unnecessary remote bodies in the plan.**
- [ ] **Step 4: Add stale-observation validation to the plan/apply contract.**
- [ ] **Step 5: Run focused tests and commit the plan slice.**

### Task 4: Apply imports and commit once at the end

**Files:**
- Modify: `src/jobutils/sync/engine.py`
- Modify: `src/jobutils/cli.py`
- Modify: `tests/test_sync.py`
- Modify: `spec/sync/plan-apply.md`
- Modify: `spec/git/local-operations.md`

**Interfaces:**
- `apply_plan` handles publish actions and observation-backed import actions.
- Conflict actions fail before any external write or local mutation.
- CLI `sync apply` performs one commit after successful actions and one push afterward.

- [ ] **Step 1: Write failing tests** for import application, conflict blocking, and exactly one post-apply commit before push.
- [ ] **Step 2: Run focused tests and confirm failure.**
- [ ] **Step 3: Implement import application using the existing three-way merge and metadata materialization logic.**
- [ ] **Step 4: Remove the pre-apply commit and retain final commit/push behavior.**
- [ ] **Step 5: Run focused tests and commit the apply slice.**

### Task 5: Remove the normal `sync pull` surface and update Vim/docs

**Files:**
- Modify: `vim/plugin/jobutils_gtd.vim`
- Modify: `vim/autoload/jobutils/gtd.vim`
- Modify: `tests/test_vim_runtime.py`
- Modify: `docs/setup/README.md`
- Modify: `docs/usage/README.md`
- Modify: `spec/user-workflow.md`
- Modify: `docs/design/implementation-roadmap.md`

**Interfaces:**
- Normal user commands are `GtdSyncCheck`, `GtdSyncPlan`, and `GtdSyncApply` plus status/rebind/check helpers.
- `GtdSyncCheck` asks for confirmation before refreshing Git/Jira/Confluence.
- No normal Vim or CLI command exposes `sync pull`.

- [ ] **Step 1: Write failing Vim/documentation tests** for the reduced command surface and check confirmation.
- [ ] **Step 2: Run focused tests and confirm failure.**
- [ ] **Step 3: Remove pull registration/aliases and wire check confirmation and messages.**
- [ ] **Step 4: Rewrite daily usage and normative workflow docs to show check → plan → apply.**
- [ ] **Step 5: Run focused tests and commit the user workflow slice.**

### Task 6: Full verification and PR update

**Files:**
- Verify: all changed source, specs, docs, and tests.

- [ ] **Step 1: Run the full unittest suite, Python compilation, shell syntax checks, and `git diff --check`.**
- [ ] **Step 2: Inspect staged content for credentials, personal paths, project-specific values, and stale `sync pull` user instructions.**
- [ ] **Step 3: Run the sanitize-artifacts review on user-facing docs and revise any process residue.**
- [ ] **Step 4: Push the feature branch and update PR #13 without merging it.**

## Self-review checklist

- The plan has one clear workflow and no separate Git/Atlassian pull command for users.
- Check refreshes both local remote metadata and external records before planning.
- Apply is the only normal operation that commits and pushes.
- Conflict handling remains explicit and resolvable in Vim.
- The observation cache is ignored and contains no credentials.
