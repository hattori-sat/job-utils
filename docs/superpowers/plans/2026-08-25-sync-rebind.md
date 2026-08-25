# Synchronization Relationship Hardening Implementation Plan

**Goal:** Make external parent relationships reliable when a Jira parent is created in the same apply operation, and provide a safe way to update stored Jira/Confluence identities or parent bindings.

**Architecture:** Markdown front matter remains the local source of truth. Plan generation records explicit relationship paths, apply resolves those paths in dependency order, and a read-only local rebind operation updates only validated identity fields. Vim exposes the same rebind workflow through the existing synchronization command family.

**Tech Stack:** Python 3.8+ standard library, classic Vimscript, JSON plans, YAML front matter, unittest.

**Spec:** `spec/sync/rebind.md`, `spec/sync/plan-apply.md`, `spec/gtd/markdown-format.md`

## Global Constraints

- Keep the GTD Repository separate from job-utils.
- Never write credentials, tokens, or private Markdown paths into plans or external payloads.
- Never call an external API during local rebind.
- Reject unsafe paths and invalid identity values before changing a file.
- Keep Jira and Confluence parent relationships explicit and cycle-safe.
- Use the classic Vim workflow and preserve lowercase command aliases.

---

### Task 1: Specify and test local identity rebinding

**Files:**
- Create: `spec/sync/rebind.md`
- Modify: `src/jobutils/sync/engine.py`
- Modify: `src/jobutils/cli.py`
- Test: `tests/test_sync.py`

**Interfaces:**
- `rebind(repo_root: Path, relative_path: str, kind: str, external_id: str, url: Optional[str] = None, parent_id: Optional[str] = None) -> Path` validates a managed Markdown file and updates only the selected external identity fields.
- CLI command: `jobutils sync rebind --repo REPO --path MANAGED.md --kind jira|confluence --external-id ID [--url URL] [--parent-id ID]`.

- [x] Write tests for Jira key/URL rebinding, Confluence page ID/URL/parent ID rebinding, and rejection of missing files, unsafe paths, invalid kinds, empty IDs, and external URLs with unsafe schemes.
- [x] Run the focused sync tests and verify the new tests fail because the public function and CLI command do not exist.
- [x] Define the command's field mapping and validation rules in `spec/sync/rebind.md`.
- [x] Implement atomic front matter updates through the existing managed-path and URL validation seams; do not contact Jira or Confluence.
- [x] Run the focused sync tests and verify all rebind cases pass.
- [x] Commit as `feat: add safe external identity rebinding`.

### Task 2: Resolve Jira parent dependencies during apply

**Files:**
- Modify: `src/jobutils/gtd/dispatcher.py`
- Modify: `src/jobutils/sync/engine.py`
- Modify: `spec/gtd/markdown-format.md`
- Test: `tests/test_gtd_dispatch.py`
- Test: `tests/test_sync.py`

**Interfaces:**
- Child task front matter may carry `jira_parent_path` in addition to `jira_parent_key`.
- `create_plan()` records a safe Jira `parent_path` for a child task and orders the parent action before the child action.
- `apply_plan()` resolves a Jira parent key from a newly-created parent result or an existing parent Markdown file before invoking the child adapter.

- [x] Add tests for a published parent without `jira_key`, a published child with `jira_parent_path`, parent-first plan ordering, and child payloads receiving the created Jira key.
- [x] Run the focused dispatch and sync tests and verify the new dependency tests fail.
- [x] Add `jira_parent_path` to task templates and inherit `publish_jira`, project, and sub-task issue type without requiring the parent key to already exist.
- [x] Infer the parent path for existing nested task files when the explicit field is absent, while rejecting unsafe or cyclic relationships.
- [x] Generalize apply dependency resolution to Jira and Confluence without changing manual `jira_parent_key` behavior.
- [x] Run the focused tests and verify unresolved parents fail before any child write.
- [x] Commit as `feat: resolve Jira parent dependencies`.

### Task 3: Add Vim command and documentation surfaces

**Files:**
- Modify: `vim/plugin/jobutils_gtd.vim`
- Modify: `vim/autoload/jobutils/gtd.vim`
- Modify: `docs/setup/README.md`
- Modify: `spec/sync/plan-apply.md`
- Test: `tests/test_vim_runtime.py`

**Interfaces:**
- `:GtdSyncRebind [path]` prompts for target kind, external ID, URL, and optional parent ID; lowercase `:gtdsyncrebind` behaves identically.
- With no path, the current managed Markdown buffer is used; the Python command remains available for scripts and recovery.

- [ ] Add Vim runtime tests for command registration, lowercase alias, current-buffer path derivation, and cancellation without file mutation.
- [ ] Run the focused Vim tests and verify the new command tests fail.
- [ ] Implement the Vim wrapper using the existing confirmation/error display helpers and the Python `sync rebind` command.
- [ ] Document when to use rebind, how parent IDs are updated, and how to regenerate/apply a plan afterward.
- [ ] Run all Vim and sync tests and verify the command help remains consistent.
- [ ] Commit as `feat: expose sync rebind in Vim`.

### Task 4: Sanitize, review, and prepare the PR

**Files:**
- Modify: `docs/design/implementation-roadmap.md`
- Modify: this plan file

- [ ] Update the roadmap and setup guide to distinguish local rebind from external apply.
- [ ] Run the complete test suite and `git diff --check`.
- [ ] Scan the public diff for credentials, real Atlassian identifiers, local user paths, generated output, and production-process residue.
- [ ] Request code review and resolve all Critical/Important findings.
- [ ] Commit the final documentation/review changes, push only `codex/pr-sync-rebind`, and open one PR against `main`; do not merge it.
