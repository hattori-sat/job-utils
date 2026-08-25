# External Drift Check Implementation Plan

**Goal:** Add a read-only synchronization check that reports whether local Markdown, the last synchronized base, and Jira/Confluence currently agree.

**Architecture:** Reuse the existing parser, stored base snapshots, and adapter fetch boundary. A pure classifier maps the three public bodies to stable states; the CLI and classic Vim expose the result without changing Markdown, front matter, plans, or external systems.

**Tech Stack:** Python 3.8+ standard library, JSON output, classic Vimscript, unittest.

**Spec:** `spec/sync/check.md`, `spec/sync/plan-apply.md`, `docs/research/plan-apply-design.md`

## Global Constraints

- Markdown in the separate GTD Repository remains the local source of truth.
- The check never writes Jira, Confluence, Markdown, front matter, plans, or base snapshots.
- Credentials remain in the environment and never appear in output.
- A missing base is reported as unknown rather than guessed as clean.
- Fetch errors are reported per item and do not abort checks for unrelated items.
- Preserve classic Vim and lowercase command aliases.

---

### Task 1: Define and test drift classification

**Files:**
- Create: `spec/sync/check.md`
- Modify: `src/jobutils/sync/engine.py`
- Test: `tests/test_sync.py`

**Interfaces:**
- `classify_drift(base: Optional[str], local: str, remote: str) -> str` returns `clean`, `external_changed`, `local_changed`, `conflict`, `converged`, or `unknown`.
- `check(repo_root: Path, adapter: SyncAdapter) -> Dict[str, object]` returns `checked`, `items`, and `error_count` without mutating the repository.

- [x] Write tests for all classifier states, missing bases, private Implementation Notes, and a fetch error isolated to one item.
- [x] Run the focused tests and verify they fail because the public classifier and check operation do not exist.
- [x] Specify the state meanings and JSON shape in `spec/sync/check.md`.
- [x] Implement the pure classifier and read-only repository scan using the existing `_documents`, `parse_document`, `_base_path`, and adapter fetch boundaries.
- [x] Ensure each item includes its relative path, kind, external ID, state, and external URL when available; include an error message only for that item.
- [x] Run focused sync tests and verify no Markdown or `.jobutils` files change.
- [x] Commit as `feat: add read-only sync drift check`.

### Task 2: Add CLI and Vim entry points

**Files:**
- Modify: `src/jobutils/cli.py`
- Modify: `vim/plugin/jobutils_gtd.vim`
- Modify: `vim/autoload/jobutils/gtd.vim`
- Modify: `docs/setup/README.md`
- Modify: `spec/sync/plan-apply.md`
- Test: `tests/test_vim_runtime.py`

**Interfaces:**
- CLI: `jobutils sync check --repo PATH --adapter memory|atlassian`, printing one JSON object.
- Vim: `:GtdSyncCheck` and `:gtdsynccheck`, displaying the JSON summary in `:messages` without confirmation.

- [x] Add CLI tests for memory-adapter classification and error exit behavior when any item fails.
- [x] Add Vim runtime tests for command registration, lowercase alias, read-only invocation, and message output.
- [x] Run the focused CLI/Vim tests and verify the new entry points fail before implementation.
- [x] Implement the CLI adapter selection and Vim wrapper through the existing `s:run_cli`, `s:show_output`, and `s:show_error` helpers.
- [x] Document the check-before-plan workflow and distinguish it from `sync pull`.
- [x] Run all sync and Vim tests and commit as `feat: expose sync drift check`.

### Task 3: Sanitize, review, and prepare the PR

**Files:**
- Modify: `docs/design/implementation-roadmap.md`
- Modify: this plan file

- [x] Add read-only drift checking to the roadmap and setup guidance.
- [x] Run the complete test suite and `git diff --check`.
- [x] Scan the public diff for credentials, real Atlassian identifiers, local user paths, generated output, and production-process residue.
- [x] Request code review and resolve all Critical/Important findings.
- [ ] Commit the final documentation state, push only `codex/pr-sync-drift`, and open one PR against `main`; do not merge it.
