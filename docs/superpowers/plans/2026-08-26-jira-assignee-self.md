# Jira Self-Assignee Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Assign newly created Jira issues to the authenticated Jira user by default without changing assignees on existing issues.

**Architecture:** Add a non-secret `JIRA_ASSIGN_TO_SELF` synchronization default. When enabled, the Atlassian adapter reads the authenticated user's `accountId` from Jira REST API v2 `/myself` and includes `assignee: {accountId: ...}` in the create request. Updates remain unchanged.

**Tech Stack:** Python 3.8+ standard library, existing `urllib.request` adapter, YAML front matter defaults, `unittest`.

**Spec:** `docs/setup/environment-variables.md`, `spec/sync/plan-apply.md`

## Global Constraints

- `JIRA_ASSIGN_TO_SELF` defaults to `true` for new Jira issues.
- Existing Jira issues are never reassigned by an ordinary Markdown update.
- The current user's `accountId` is not written to Markdown, plans, logs, or reports.
- `/rest/api/2/myself` is read-only and uses the existing Jira authentication mode.
- A failed self-assignee lookup fails before the issue-create request is sent.
- Confluence synchronization is unchanged.

---

### Task 1: Configuration and payload

**Files:** `.env.example`, `src/jobutils/setup_workflow.py`,
`src/jobutils/sync/defaults.py`, `src/jobutils/sync/engine.py`.

- [x] Add `JIRA_ASSIGN_TO_SELF=true` to setup and synchronization defaults.
- [x] Add `assign_to_self` to Jira create payloads, with optional front matter override.

### Task 2: Jira adapter

**Files:** `src/jobutils/sync/adapters.py`,
`tests/test_atlassian_adapter.py`.

- [x] Resolve and cache the current user's `accountId` through `GET /rest/api/2/myself`.
- [x] Include `assignee: {accountId: ...}` only in new Jira issue creation.
- [x] Stop before issue creation when the lookup fails or has no account ID.
- [x] Keep the account ID in memory only.

### Task 3: Documentation and verification

**Files:** setup/usage docs, synchronization specs, and this plan.

- [x] Document the default, opt-out, and update behavior.
- [x] Add tests for enabled, disabled, default, and failure paths.
- [ ] Run full tests, compile checks, shell checks, and `git diff --check`.
- [ ] Commit on a `codex/*` branch and create a PR without merging.
