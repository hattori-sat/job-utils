# Atlassian Bearer and Jira v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Jira synchronization use REST API v2 with Bearer authentication by default while retaining explicit Basic compatibility and safe diagnostics.

**Architecture:** Keep authentication in the shared Atlassian HTTP adapter, with separate Jira and Confluence auth-type environment variables. Keep Confluence storage conversion unchanged; add a Jira wiki-text conversion boundary so the engine emits strings for Jira v2 and imports both wiki text and legacy ADF safely.

**Tech Stack:** Python standard library, `urllib.request`, unittest, Markdown normalization helpers, Jira Cloud REST API v2, Confluence Cloud REST API v2.

**Spec:** `spec/sync/atlassian-auth-and-jira-v2.md`

## Global Constraints

- Jira issue endpoints use `/rest/api/2`.
- Confluence endpoints remain `/wiki/api/v2`.
- Bearer is the default authentication type.
- Basic remains available only when explicitly selected.
- Tokens must never appear in source, tests, plans, logs, or error text.
- Do not modify `.env` or contact Jira/Confluence during local tests.

---

### Task 1: Add failing conversion and adapter tests

**Files:**
- Modify: `tests/test_markdown_conversion.py`
- Modify: `tests/test_sync.py`
- Create: `tests/test_atlassian_adapter.py`

- [x] Write tests for Markdown wiki conversion, Jira payload string descriptions, v2 endpoint paths, Bearer and Basic headers, and bounded HTTP error details.
- [x] Run the focused tests and confirm they fail against the current ADF/Basic/v3 implementation.

### Task 2: Implement Jira v2 text conversion

**Files:**
- Modify: `src/jobutils/markdown/normalize.py`
- Modify: `src/jobutils/sync/engine.py`

- [x] Add deterministic `markdown_to_jira_wiki` and `jira_wiki_to_markdown` helpers for supported headings, paragraphs, lists, tables, code blocks, links, and plain macro text.
- [x] Change Jira plan payloads from `description_adf` to a string `description`.
- [x] Accept Jira v2 strings on import and retain defensive ADF import support.
- [x] Run conversion and sync tests.

### Task 3: Implement configurable Bearer authentication and diagnostics

**Files:**
- Modify: `src/jobutils/sync/adapters.py`
- Modify: `.env.example`
- Modify: `src/jobutils/setup_workflow.py`
- Modify: `docs/setup/environment-variables.md`

- [x] Add `JIRA_AUTH_TYPE` and `CONFLUENCE_AUTH_TYPE`, defaulting to `bearer`.
- [x] Emit Bearer headers by default and Basic headers when explicitly selected.
- [x] Make email required only for Basic authentication.
- [x] Catch HTTP errors and include service, method, path, status, and a bounded response body without credentials.
- [x] Run adapter and setup tests.

### Task 4: Verify and document the workflow

**Files:**
- Modify: `docs/setup/README.md`
- Modify: `docs/usage/README.md`
- Modify: `spec/sync/plan-apply.md`

- [x] Document Bearer defaults, Basic override, Jira v2, and the safe 401/403 troubleshooting path.
- [x] Run the full suite, compile checks, shell checks, `git diff --check`, and sensitive-value scan.
- [ ] Commit the feature and update the existing PR branch without merging.
