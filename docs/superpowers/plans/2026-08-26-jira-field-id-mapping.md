# Jira Field ID Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Treat Jira Summary, Description, and Progress Comment as explicit field-ID mappings with safe defaults and consistent create, update, and import behavior.

**Architecture:** Keep Markdown as the source of truth. Resolve `summary` and `description` through non-secret synchronization defaults, allow per-task front matter overrides, and pass the resolved field IDs through the adapter boundary. Store all synchronization JSON under the separate GTD Markdown Repository's `.jobutils/` directory.

**Tech Stack:** Python 3.8+ standard library, classic Vim workflow, YAML front matter, JSON state, `unittest`.

**Spec:** `spec/sync/plan-apply.md`, `spec/gtd/markdown-format.md`

## Global Constraints

- Jira's default system field IDs are `summary` and `description`.
- `Progress Comment` remains an optional configured Jira field ID.
- Front matter values override `.env` defaults; `.env` values never enter plans as credentials.
- Markdown remains the canonical source and external IDs/state remain in the separate GTD Markdown Repository.
- Runtime operation has safe `summary` and `description` fallbacks; setup may confirm the IDs through Jira's read-only field catalog.
- Existing task and synchronization behavior must remain compatible when the new fields are absent.

---

### Task 1: Add failing tests for field resolution and adapter mappings

**Files:**
- Modify: `tests/test_sync.py`
- Modify: `tests/test_atlassian_adapter.py`

**Interfaces:**
- `load_sync_defaults()` returns `jira_summary_field` and `jira_description_field`.
- Jira payloads expose `summary_field` and `description_field`.
- Adapter fetch options may contain `summary_field` and `description_field`.

- [x] Add tests that absent configuration resolves to `summary` and `description`.
- [x] Add tests that front matter values override environment defaults in the plan payload.
- [x] Add tests that Jira create/update writes the resolved IDs and fetch reads the resolved IDs.
- [x] Run the focused tests and confirm the new assertions fail before implementation.

### Task 2: Implement defaults, front matter, and adapter field mapping

**Files:**
- Modify: `src/jobutils/sync/defaults.py`
- Modify: `src/jobutils/sync/engine.py`
- Modify: `src/jobutils/sync/adapters.py`
- Modify: `src/jobutils/markdown/normalize.py`
- Modify: `src/jobutils/gtd/dispatcher.py`
- Modify: `src/jobutils/setup_workflow.py`
- Modify: `.env.example`

**Interfaces:**
- `load_sync_defaults() -> Dict[str, str]` supplies the standard IDs.
- `_payload(..., "jira")` supplies `summary_field` and `description_field`.
- `SyncAdapter.fetch(..., options)` uses the same resolved IDs when importing.

- [x] Add `JIRA_SUMMARY_FIELD=summary` and `JIRA_DESCRIPTION_FIELD=description` to setup configuration.
- [x] Add `jira_summary_field` and `jira_description_field` to task front matter parsing and generated templates.
- [x] Resolve front matter first, then environment, then standard IDs.
- [x] Use resolved field IDs for Jira create/update and external-to-Markdown import.
- [x] Preserve fallback reading of standard keys for older observations and plans.
- [x] Run focused tests and confirm they pass.

### Task 3: Update normative documentation and verify repository state

**Files:**
- Modify: `spec/gtd/markdown-format.md`
- Modify: `spec/sync/plan-apply.md`
- Modify: `docs/setup/environment-variables.md`
- Modify: `docs/setup/config.example.yaml`
- Modify: `docs/usage/README.md`

- [x] Document the default and override rules for Jira field IDs.
- [x] Document that sync JSON and JSONL files live under the separate GTD Repository `.jobutils/` directory.
- [ ] Run the full test suite, compile checks, and `git diff --check`.
- [ ] Scan the diff for credentials, personal Atlassian values, and unrelated files.
- [ ] Commit the feature on a `codex/*` branch without pushing or merging.
