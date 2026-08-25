# Real Git Push Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit, real Git push operation for the separate GTD Markdown repository so local commits can be synchronized across machines.

**Architecture:** Keep Git operations in `jobutils.gitops`. Add a real push path that invokes Git without a shell, uses the repository's configured remote and credentials, rejects dirty worktrees, and never force-pushes. Keep `push-mock` as a no-network dry-run path. Expose the real operation through the CLI and Vim, and make confirmed Atlassian sync apply commit and push the resulting local state. Remove the unused local HTTP server surface.

**Tech Stack:** Python 3.8-compatible standard library, Git CLI, classic Vimscript, unittest.

**Spec:** `spec/git/local-operations.md`

## Global Constraints

- The GTD Markdown Repository remains separate from job-utils.
- The real push operation must not use a shell, force-push, or embed credentials.
- A dirty working tree must fail before any remote operation.
- `push-mock` remains available for deterministic tests and dry runs.
- Atlassian sync apply must commit and push generated local synchronization state.
- No background or local HTTP server is part of the workflow.
- Main repository changes must continue through a feature branch and PR.

---

### Task 1: Implement a real Git push boundary

**Files:**
- Modify: `src/jobutils/gitops.py`
- Test: `tests/test_gitops.py`

**Interfaces:**
- Consumes: a local Git working tree, configured remote name, and optional branch name.
- Produces: `push(repo_root, remote="origin", branch="", set_upstream=False)` returning a JSON-safe dictionary with `performed`, `remote`, `branch`, `revision`, and captured Git output.

- [ ] **Step 1: Write the failing tests**

Add tests using a temporary bare repository as the remote. Verify that a clean committed repository pushes a new branch, that a dirty worktree fails before the remote changes, and that the command does not include `--force`.

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `PYTHONPATH=src python3 -m unittest tests.test_gitops -v`

Expected: FAIL because the real `push` function does not exist.

- [ ] **Step 3: Implement the minimal push operation**

Use `_run(repo_root, ["push", ...])` with a configured remote and current branch fallback. Reject a dirty worktree, empty branch, missing remote, and nonzero Git exit status. Do not expose environment values or credentials in the returned result.

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `PYTHONPATH=src python3 -m unittest tests.test_gitops -v`

Expected: all Git operation tests pass, including verification that the bare remote received the commit.

- [ ] **Step 5: Commit**

```bash
git add src/jobutils/gitops.py tests/test_gitops.py
git commit -m "feat: add real git push operation"
```

### Task 2: Make Atlassian sync apply commit and push

**Files:**
- Modify: `src/jobutils/cli.py`
- Modify: `tests/test_sync.py`
- Modify: `spec/sync/plan-apply.md`

**Interfaces:**
- Consumes: Task 1's `gitops.commit` and `gitops.push` functions.
- Produces: Atlassian `sync apply` defaulting to external apply → local commit → real push, with `--no-git-sync` for controlled recovery and `--git-sync` for deterministic non-Atlassian integration tests.

- [x] **Step 1: Write the failing integration test**

The test uses a local bare repository as the remote and verifies that a Memory adapter apply with `--git-sync` creates a local commit and transfers the same revision to the remote.

- [x] **Step 2: Run the focused test to verify it fails**

The test initially failed because the CLI had no Git synchronization phase.

- [x] **Step 3: Implement the synchronization phase**

The CLI checks for a clean worktree before external apply, commits generated metadata after a successful apply, and performs the real push. A push failure leaves the local commit available for retry.

- [x] **Step 4: Run the focused test to verify it passes**

The local bare-remote integration test passed.

- [ ] **Step 5: Commit**

```bash
git add src/jobutils/cli.py tests/test_sync.py spec/sync/plan-apply.md
git commit -m "feat: synchronize local state after external apply"
```

### Task 3: Expose the operation through CLI and Vim

**Files:**
- Modify: `src/jobutils/cli.py`
- Modify: `vim/autoload/jobutils/gtd.vim`
- Modify: `vim/plugin/jobutils_gtd.vim`
- Test: `tests/test_gitops.py`
- Test: `tests/test_vim_runtime.py`

**Interfaces:**
- Consumes: Task 1's `gitops.push` function.
- Produces: `jobutils git push --repo REPOSITORY [--remote origin] [--branch BRANCH] [--set-upstream]` and `:GtdGitPush [remote] [branch]` with lowercase alias `:gtdgitpush`.

- [ ] **Step 1: Write the failing CLI and Vim tests**

Assert that the CLI parser exposes `git push`, that the Vim runtime contains the command and lowercase abbreviation, and that the Vim wrapper invokes `jobutils git push` rather than `push-mock`.

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `PYTHONPATH=src python3 -m unittest tests.test_gitops tests.test_vim_runtime -v`

Expected: FAIL because only `push-mock` is exposed.

- [ ] **Step 3: Implement the CLI and Vim wrappers**

Add the explicit CLI operation and JSON output. The Vim command must require a clean/committed repository through the Python boundary and display Git errors in Vim's existing error surface.

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `PYTHONPATH=src python3 -m unittest tests.test_gitops tests.test_vim_runtime -v`

Expected: all focused tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/jobutils/cli.py vim/autoload/jobutils/gtd.vim vim/plugin/jobutils_gtd.vim tests/test_gitops.py tests/test_vim_runtime.py
git commit -m "feat: expose git push in cli and vim"
```

### Task 4: Remove the unnecessary local HTTP server

**Files:**
- Delete: `src/jobutils/server.py`
- Delete: `tests/test_server.py`
- Delete: `spec/server/local-http.md`
- Modify: `src/jobutils/cli.py`
- Modify: `docs/design/document-map.md`
- Modify: `docs/setup/README.md`

**Interfaces:**
- Consumes: the Vim-centered CLI and actual Git synchronization workflow.
- Produces: no `serve` command, no resident/local HTTP process, and no server-specific documentation or tests.

- [x] **Step 1: Remove the unused server entry points and tests**
- [x] **Step 2: Verify the CLI and documentation no longer advertise `serve`**
- [ ] **Step 3: Commit**

```bash
git add -u src/jobutils/server.py tests/test_server.py spec/server/local-http.md src/jobutils/cli.py docs/design/document-map.md docs/setup/README.md
git commit -m "remove: drop unused local http server"
```

### Task 5: Update the user-facing workflow and verify integration

**Files:**
- Modify: `spec/git/local-operations.md`
- Modify: `docs/setup/README.md`
- Modify: `docs/setup/platform-notes.md`
- Test: `tests/test_setup_docs.py`

**Interfaces:**
- Consumes: the CLI and Vim interfaces from Task 2.
- Produces: documented workflow: sync plan → confirmed external apply → local commit → explicit real Git push.

- [ ] **Step 1: Update the normative specification**

Document real push behavior, safety checks, credential handling through Git's own credential helpers, and the retained `push-mock` dry-run operation.

- [ ] **Step 2: Update setup and command documentation**

Replace the claim that push is unavailable with the explicit command sequence and explain that setup still does not create remotes or push automatically.

- [ ] **Step 3: Run documentation and full tests**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v`

Expected: all tests pass, with server integration tests run in an environment that permits localhost sockets.

- [ ] **Step 4: Run repository hygiene checks**

Run: `git diff --check` and inspect the staged diff for credentials, personal paths, and workspace-specific project identifiers.

- [ ] **Step 5: Commit**

```bash
git add spec/git/local-operations.md docs/setup/README.md docs/setup/platform-notes.md tests/test_setup_docs.py
git commit -m "docs: document real git synchronization workflow"
```

## Self-review

- The plan covers the real push implementation, CLI/Vim entry points, tests, and user documentation.
- It does not add a background server or automatic push.
- It preserves a mock path for tests and dry runs.
- It leaves Jira/Confluence apply as a separate explicit operation and adds the missing local Git synchronization step afterward.
