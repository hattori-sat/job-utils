# Jira Data Center Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Jira Cloud/Data Center selection so Jira Data Center creates, updates, fetches, and self-assigns with the Data Center `name` field while preserving the existing Confluence platform selection.

**Architecture:** Keep the existing Cloud Jira/Confluence adapter unchanged for the Cloud path. Add a Jira Data Center adapter that reuses the REST v2 issue payload and conversion logic but uses Data Center credentials and `assignee: {"name": ...}`; compose independent Jira and Confluence adapters when either platform is Data Center. `sync check` and `sync apply` use the selected composite, while Confluence Data Center remains upload-only.

**Tech Stack:** Python standard library, `urllib.request`, environment-file setup, unittest, Jira REST API v2, Confluence Cloud REST API v2, Confluence Data Center Content REST API.

**Spec:** `spec/sync/atlassian-auth-and-jira-v2.md`, `spec/sync/plan-apply.md`, `spec/sync/confluence-datacenter-upload.md`

## Global Constraints

- Keep Jira and Confluence platform selection independent; default both to Cloud.
- Preserve `JIRA_AUTH_TYPE` and `CONFLUENCE_AUTH_TYPE`; never print or serialize credentials.
- Jira Cloud uses `accountId` for self-assignment; Jira Data Center uses `name`.
- Existing Jira updates do not change the assignee.
- Data Center Confluence remains upload-only and must not issue a page GET during check.
- Run focused tests, the full suite, and `git diff --check` before commit.

---

### Task 1: Specify platform and credential configuration

**Files:**
- Modify: `.env.example`
- Modify: `src/jobutils/setup_workflow.py:20-65,350-385`
- Modify: `docs/setup/environment-variables.md`
- Modify: `spec/sync/atlassian-auth-and-jira-v2.md`
- Modify: `spec/sync/plan-apply.md`
- Test: `tests/test_setup_profiles.py`, `tests/test_setup_workflow.py`

**Interfaces:**
- Produces `JIRA_PLATFORM=cloud|datacenter` with default `cloud`.
- Produces optional `JIRA_USERNAME` for Jira Data Center Basic authentication and self-assignment.
- Keeps existing Cloud setup prompts and values backward compatible.

- [x] **Step 1: Write failing setup tests** for platform validation, generated defaults, and Data Center username configuration.
- [x] **Step 2: Run the focused setup tests and confirm the new expectations fail.**
- [x] **Step 3: Add `JIRA_PLATFORM` and `JIRA_USERNAME` to setup configuration with validation and non-secret documentation.**
- [x] **Step 4: Run the focused setup tests and confirm they pass.**

### Task 2: Add Jira Data Center adapter and independent routing

**Files:**
- Modify: `src/jobutils/sync/adapters.py:120-440,545-580`
- Modify: `src/jobutils/cli.py:185-220`
- Test: `tests/test_atlassian_adapter.py`, `tests/test_sync.py`

**Interfaces:**
- Produces `JiraDataCenterAdapter(SyncAdapter)` with inherited Jira issue create/update/fetch behavior and Data Center self-assignment.
- Produces a composite Atlassian adapter that routes Jira and Confluence independently and exposes `upload_only_kinds` for Confluence Data Center.
- `_build_atlassian_adapter(..., for_apply=True)` and check use `JIRA_PLATFORM` plus `CONFLUENCE_PLATFORM`.

- [x] **Step 1: Write failing adapter tests** asserting Jira Data Center self-assignment sends `{"name": ...}`, Basic auth can use `JIRA_USERNAME`, and Cloud still sends `{"accountId": ...}`.
- [x] **Step 2: Write failing routing tests** for Jira Data Center + Confluence Cloud, Jira Data Center + Confluence Data Center, and the existing Cloud + Data Center combination.
- [x] **Step 3: Run the focused adapter and routing tests and confirm they fail.**
- [x] **Step 4: Implement the Data Center Jira adapter and composite routing with no credential leakage.**
- [x] **Step 5: Run the focused adapter and routing tests and confirm they pass.**

### Task 3: Validate sync behavior and user-facing workflow

**Files:**
- Modify: `docs/usage/README.md`
- Modify: `spec/gtd/markdown-format.md`
- Modify: `spec/user-workflow.md`
- Test: `tests/test_sync.py`, `tests/test_vim_runtime.py`

**Interfaces:**
- Jira Data Center uses the same `GtdSyncCheck → GtdSyncPlan → GtdSyncApply` workflow.
- `JIRA_ASSIGN_TO_SELF=true` performs a Jira Data Center current-user lookup and sends the returned `name` only on create.
- Jira Data Center external IDs remain issue keys such as `ABC-123`; subtask parents continue using `parent: {"key": ...}`.

- [x] **Step 1: Write failing sync tests** for Jira Data Center check, create, update, external ID handling, and subtask parent keys.
- [x] **Step 2: Run the focused sync tests and confirm they fail.**
- [x] **Step 3: Update workflow/spec documentation to distinguish Jira Data Center from Confluence Data Center.**
- [x] **Step 4: Run the focused sync/Vim tests and confirm they pass.**

### Task 4: Full verification and delivery

**Files:**
- Modify: `docs/research/gtd-sync-cloud-live-validation-2026-08-27.md`

- [x] **Step 1: Run the full test suite and `git diff --check`.**
- [x] **Step 2: Run a redacted live smoke test against the configured Jira Cloud/Confluence Cloud resources without changing protected records.**
- [x] **Step 3: If a Jira Data Center endpoint is configured, run create/update/check using only an explicitly permitted test issue; otherwise record the live Jira Data Center test as UNKNOWN.**
- [x] **Step 4: Inspect staged files for secrets, personal data, generated output, and unrelated files.**
- [x] **Step 5: Commit and push the implementation to the feature PR branch.**
