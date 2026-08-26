# External Vim Swap Directory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep Vim swap recovery enabled while storing swap files outside the GTD Markdown Repository.

**Architecture:** Configure the classic Vim runtime to create a per-user swap directory under `~/.vim/swap` on macOS/Ubuntu and `%LOCALAPPDATA%/vim/swap` on Windows. Create the directory with restrictive permissions when possible and preserve the existing `.gitignore` defense for old repository-local swap files.

**Tech Stack:** Classic Vimscript, platform environment variables, existing Vim runtime tests.

**Spec:** `docs/setup/README.md`, `docs/research/vim-workflow-settings.md`

## Global Constraints

- Do not disable swap files globally.
- Do not create swap files in the GTD Markdown Repository during normal use.
- Preserve recover prompts and stale-swap detection.
- Keep Makefile literal-tab and existing filetype behavior unchanged.

---

### Task 1: Add a red-capable Vim runtime test

**Files:**
- Modify: `tests/test_vim_runtime.py`

- [x] Add a test that sources the runtime with an isolated `HOME` and asserts `&directory` contains the user swap directory.
- [x] Assert the swap directory exists outside the edited Markdown repository.
- [x] Run the focused test and confirm it fails before implementation.

### Task 2: Configure the external swap directory

**Files:**
- Modify: `vim/plugin/jobutils_defaults.vim`

- [x] Select `~/.vim/swap` on macOS/Ubuntu and `$LOCALAPPDATA/vim/swap` on Windows.
- [x] Create the directory with `mkdir(..., 'p', 0700)` when absent.
- [x] Add the directory with Vim's double-slash filename encoding and retain swap files.
- [x] Run the focused test and confirm it passes.

### Task 3: Document and verify

**Files:**
- Modify: `docs/setup/README.md`
- Modify: `docs/research/vim-workflow-settings.md`
- Modify: `docs/superpowers/plans/2026-08-26-vim-external-swap-directory.md`

- [x] Explain that swap remains enabled for recovery but is stored outside the data repository.
- [x] Run the focused Vim tests; add coverage for `XDG_STATE_HOME`.
- [ ] Run the full test suite, Vim tests, compile checks, and `git diff --check`.
- [ ] Commit locally without push, PR, or merge.
