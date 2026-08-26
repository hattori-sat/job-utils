# Setup Jira Standard Field Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make setup discover the Jira Summary and Description field IDs and write them into the local `.env` without attempting to guess the user-specific Progress Comment custom field.

**Architecture:** Keep setup non-destructive and resumable. After `.env` is created or completed, perform a read-only Jira field-catalog request using the configured authentication, select exact case-insensitive `Summary` and `Description` matches, and write only default or empty `JIRA_SUMMARY_FIELD` and `JIRA_DESCRIPTION_FIELD` values. `JIRA_PROGRESS_COMMENT_FIELD` remains manual because its name and identity are user-specific. Discovery failures are warnings recorded in setup state, not reasons to destroy or overwrite a working setup.

**Tech Stack:** Python 3.8+ standard library, `urllib.request`, JSON, hidden token environment, `unittest`.

**Spec:** `docs/setup/environment-variables.md`, `spec/sync/plan-apply.md`

## Global Constraints

- Existing non-default `JIRA_SUMMARY_FIELD` and `JIRA_DESCRIPTION_FIELD` values are never overwritten.
- `JIRA_PROGRESS_COMMENT_FIELD` is never discovered or overwritten by setup.
- Tokens are read from `.env` or the process environment and never appear in setup output, state, or logs.
- Jira field discovery is read-only and uses `/rest/api/2/field`.
- Multiple exact-name matches are reported as ambiguous and are not auto-selected.
- Missing credentials, HTTP failures, malformed responses, and missing fields leave setup resumable.
- The separate GTD Markdown Repository remains separate; only `.env` in job-utils is updated.

---

### Task 1: Add failing setup discovery tests

**Files:**
- Modify: `tests/test_setup_workflow.py`

**Interfaces:**
- `discover_jira_standard_field_ids(job_utils_root: Path) -> Dict[str, object]`
- The function updates `.env` only when the Summary/Description values are absent or still their standard defaults.

- [x] Test exact field-name discovery writes the returned Summary and Description IDs to `.env`.
- [x] Test existing custom-configured IDs are preserved without an HTTP request.
- [x] Test `JIRA_PROGRESS_COMMENT_FIELD` is never changed by discovery.
- [x] Test ambiguous or unavailable discovery leaves the value empty and returns a safe status.
- [x] Run the focused tests and verify they fail before implementation.

### Task 2: Implement read-only Jira field discovery and setup integration

**Files:**
- Modify: `src/jobutils/setup_workflow.py`
- Modify: `src/jobutils/cli.py` only if setup output needs a new safe status field

**Interfaces:**
- `discover_jira_standard_field_ids(job_utils_root: Path) -> Dict[str, object]`
- `run_setup(...)` records a `jira_field_discovery` step after `.env` completion.

- [x] Read `.env` values without evaluating shell syntax; preserve process-environment precedence where applicable.
- [x] Build Bearer or Basic authentication exactly as the existing Atlassian adapter does, without logging credentials.
- [x] Request `GET {JIRA_BASE_URL}/rest/api/2/field` with a 30-second timeout.
- [x] Accept the documented list response and a defensive `values` response shape.
- [x] Select one exact case-insensitive `Summary` and `Description` name match, write their IDs, and chmod `.env` on POSIX.
- [x] Leave Progress Comment untouched.
- [x] Return `already_configured`, `discovered`, `not_found`, `ambiguous`, or `skipped` status without raising for remote discovery failures.
- [x] Run focused tests and verify they pass.

### Task 3: Document, verify, and commit

**Files:**
- Modify: `docs/setup/README.md`
- Modify: `docs/setup/environment-variables.md`
- Modify: `spec/sync/plan-apply.md`
- Modify: `docs/superpowers/plans/2026-08-26-setup-discover-jira-custom-fields.md`

- [x] Explain that setup auto-fills Summary and Description IDs and never overwrites manual configuration; Progress Comment remains manual.
- [x] Explain the safe outcomes for missing permission, multiple matches, and no matching field.
- [ ] Run the full test suite, compile checks, and `git diff --check`.
- [ ] Scan the staged diff for credentials and personal Atlassian values.
- [ ] Commit locally on the current `codex/*` branch; do not push, create a PR, or merge.
