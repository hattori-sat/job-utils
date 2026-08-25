# Final Integration Implementation Plan

Implementation steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the remaining user-facing integration between the separate GTD Markdown Repository, local metrics, Jira, Confluence, the Python CLI, and classic Vim.

**Architecture:** Keep the GTD Repository as the canonical source. Resolve safe Jira and Confluence defaults from the process environment at payload-build time, represent recursive document parents as local Markdown paths plus external page IDs, and resolve newly-created parent IDs during ordered apply. Treat JSONL events as the portable metrics source and derive cross-period reports without SQLite.

**Tech Stack:** Python 3.8+ standard library, classic Vimscript, JSONL, Markdown/YAML front matter, unittest.

**Spec:** `spec/gtd/markdown-format.md`, `spec/gtd/metrics-events.md`, `spec/sync/plan-apply.md`, `docs/design/sync-plan-apply.md`, `docs/design/metrics-event-model.md`

## Global Constraints

- The job-utils Repository and GTD Repository remain separate.
- Markdown and JSONL remain Git-friendly; SQLite and Docker are not required.
- `.env`, tokens, cookies, and personal Atlassian identifiers never enter plans, events, reports, or committed files.
- Jira and Confluence writes remain explicit through sync plan review and apply.
- Implementation Notes remain local-only and are excluded from external payloads.
- Confluence parent relationships must be stable across recursive child creation and page-ID rebinds.
- Classic Vim remains the user-facing editor and must call the shared Python behavior.
- Work remains on `codex/*`; no direct push or merge to `main`.

---

### Task 1: Apply workspace defaults and complete recursive document authoring

**Files:**
- Create: `src/jobutils/sync/defaults.py`
- Modify: `src/jobutils/sync/engine.py`
- Modify: `src/jobutils/markdown/normalize.py`
- Modify: `src/jobutils/gtd/documents.py`
- Modify: `src/jobutils/gtd/__init__.py`
- Modify: `src/jobutils/cli.py`
- Test: `tests/test_sync.py`
- Test: `tests/test_gtd_documents.py`

**Interfaces:**
- `load_sync_defaults() -> Dict[str, str]` reads non-secret Jira/Confluence defaults from environment variables.
- `create_subdocument(repo_root: Path, parent_path: str, line_number: int) -> Path` creates a child under the current document's directory and updates the parent `# Subdocuments` bullet.
- Document front matter includes `publish_confluence`, `parent_document_id`, `confluence_space_id`, `confluence_space_key`, `confluence_parent_id`, `confluence_parent_path`, `confluence_page_id`, `confluence_url`, and `confluence_version`.
- `create_plan()` uses front matter values first and environment defaults second. It adds an inferred `parent_path` to Confluence actions when a child document has a matching parent Markdown file.

- [x] Write tests for default Jira project/issue type/progress field and Confluence space/parent values when front matter is null or absent.
- [x] Write tests for root document creation, recursive subdocument creation, inherited publication settings, and stable `parent_document_id`/`confluence_parent_path` values.
- [x] Implement environment-default loading without importing credentials into payloads.
- [x] Extend the document template and parser metadata with external identity and parent fields.
- [x] Implement recursive `create_subdocument` with safe repository-bound paths and atomic index/parent writes.
- [x] Add `gtd subdocument --parent PATH --line N` to the CLI and export it from the GTD package.
- [x] Update `create_plan` to order parent actions before children and retain each child's local `parent_path`.
- [x] Run document and sync tests, then commit as `feat: complete document sync defaults`.

### Task 2: Resolve Confluence hierarchy during plan apply

**Files:**
- Modify: `src/jobutils/sync/engine.py`
- Modify: `src/jobutils/sync/adapters.py`
- Test: `tests/test_sync.py`

**Interfaces:**
- `apply_plan()` resolves a child action's `parent_path` from an already-created parent result or an existing parent Markdown `confluence_page_id` before calling the adapter.
- An unresolved required parent fails before the child request with `SyncError` and does not expose a local path in an external payload.
- Successful Confluence apply writes page ID, URL, version, and sync hash to the corresponding Markdown file.

- [x] Add an in-memory integration test with an unpublished parent and published child; assert the parent is created first and the child receives the returned parent ID.
- [x] Add a test for an existing parent page ID and a test for a missing parent that fails without a child adapter call.
- [x] Implement ordered action application and an in-memory path-to-external-ID map.
- [x] Keep Jira actions independent from Confluence parent resolution and preserve existing stale-plan/path validation.
- [x] Run the full sync test module and commit as `feat: resolve recursive page parents`.

### Task 3: Enrich JSONL metrics and period reports

**Files:**
- Modify: `src/jobutils/metrics/events.py`
- Modify: `src/jobutils/gtd/dispatcher.py`
- Modify: `src/jobutils/metrics/aggregate.py`
- Modify: `src/jobutils/metrics/reports.py`
- Modify: `src/jobutils/cli.py`
- Test: `tests/test_gtd_dispatch.py`
- Test: `tests/test_metrics.py`

**Interfaces:**
- Capture and state-change events carry `kind`, `tags`, `impact_level`, and `estimate_minutes` when available.
- Aggregated task rows expose `captured_at`, `first_state_at`, `lead_seconds`, `cycle_seconds`, `estimate_minutes`, `estimate_variance_seconds`, and the existing active/waiting/scheduled measures.
- Reports expose `by_tag`, `by_impact_level`, `by_prefix`, and daily throughput alongside task rows and totals.
- HTML remains self-contained and includes a period summary, grouped tables, and an inline SVG chart; CSV remains machine-readable and SVG remains standalone.

- [x] Add tests covering capture-to-completion lead time, first-committed-state cycle time, estimate variance, multi-year event files, duplicate IDs, tags, impact levels, and daily throughput.
- [x] Add tests that dispatch records the current estimate and kind without changing the existing state-transition contract.
- [x] Extend event helpers and dispatcher calls with optional measurement metadata.
- [x] Update aggregation to distinguish capture time, first committed state, completion, waiting, calendar, and active intervals without inventing missing endpoints.
- [x] Add grouped report fields and render them in CSV, HTML, and SVG with escaped user content.
- [x] Preserve on-demand output paths and add a CLI option for JSON report output used by automated analysis.
- [x] Run metrics, dispatch, and full test suites, then commit as `feat: complete task metrics reports`.

### Task 4: Add Vim document authoring and help surfaces

**Files:**
- Modify: `vim/plugin/jobutils_gtd.vim`
- Modify: `vim/autoload/jobutils/gtd.vim`
- Modify: `docs/setup/README.md`
- Modify: `spec/gtd/markdown-format.md`
- Test: `tests/test_vim_runtime.py`

**Interfaces:**
- Adds `:GtdSubdocument`/`:gtdsubdocument`, `:GtdTaskHelp`/`:gtdtaskhelp`, and `:GtdDocHelp`/`:gtddochelp`.
- `:GtdSubdocument` derives the parent document from the current buffer and requires the cursor under `# Subdocuments`.
- Help commands show accepted prefixes, tags, impact levels, publishing fields, parent fields, and the plan/apply workflow in `:messages`.

- [x] Add Vim runtime tests for subdocument creation, lowercase aliases, parent derivation, and help output.
- [x] Implement the Vim wrapper using the existing Python path/repository helpers and stable error display.
- [x] Document the full task/document distinction, recursive child workflow, defaults, and apply sequence.
- [x] Run all Vim runtime tests and commit as `feat: complete Vim authoring help`.

### Task 5: Validate, sanitize, and prepare the final integration PR

**Files:**
- Modify: `README.md`
- Modify: `docs/design/implementation-roadmap.md`
- Modify: `docs/setup/README.md`
- Modify: `docs/superpowers/plans/2026-08-25-final-integration.md`

- [x] Reconcile the roadmap and setup guide with the implemented command names and data fields.
- [x] Run the complete test suite and `git diff --check`.
- [x] Inspect the public diff for credentials, real Atlassian URLs/IDs, local paths, generated output, and user-specific configuration.
- [x] Review changed public documentation for process residue or private data and remove anything not needed by readers.
- [x] Run a final patch review and resolve all Critical/Important findings.
- [x] Push only `codex/pr-final-integration` and open one PR against `main`; do not merge it.

Verification so far: 83 tests pass, the whitespace check is clean, and the staged
public diff contains no credentials, real Atlassian identifiers, or local user
paths. The final review also covered recursive parent resolution, plan-file
handling, configured Jira defaults, and report privacy.
