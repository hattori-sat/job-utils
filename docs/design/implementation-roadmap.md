# Implementation Roadmap

job-utils is delivered in small, reviewable feature slices. The separate GTD
Repository remains the source of Markdown data throughout the roadmap.

## Current capability groups

1. **Foundation and setup**
   - Cross-platform setup for macOS, Ubuntu, and Windows.
   - Local virtual environment, `.env` initialization, wrappers, and Vim
     registration.
   - Separate job-utils and GTD repositories.

2. **GTD and Vim workflow**
   - Prefix-based movement from `gtd.md`, including Inbox returns.
   - Explicit task and document creation.
   - Subtasks and recursively nested subdocuments.
   - Classic Vim support for Markdown, JSON, XML, C, C++, CMake, and Make.

3. **Metrics and reports**
   - Git-friendly JSONL event records.
   - Active, waiting, scheduled, lead, cycle, throughput, tag, impact, and
     estimate measures.
   - On-demand HTML, CSV, and SVG reports.

4. **Content conversion**
   - Deterministic Markdown conversion for Jira ADF and Confluence storage.
   - Tables, links, images, code blocks, lists, and supported macros.
   - Local-only Implementation Notes and preserved conflict markers.

5. **External synchronization**
   - Reviewable JSON plans followed by explicit apply.
   - Jira tasks, stories, and subtasks.
   - Confluence pages, parent relationships, default values, and recursive
     child creation.
   - Pull, rebind, stale-plan detection, and two-sided conflict handling.
   - External IDs, URLs, and clickable local references in Markdown.

## Review sequence

The review sequence is:

1. Documentation and artifact hygiene.
2. Setup and command entry points.
3. GTD/Vim authoring and state transitions.
4. Metrics and report generation.
5. Markdown conversion boundaries.
6. Jira and Confluence synchronization.
7. Cross-feature integration and release verification.

Each slice has one clear purpose, focused tests, and a short user-facing
summary. A slice may depend on earlier slices, but unrelated changes remain
separate.

## Verification baseline

Before a slice is reviewed, run the focused tests for that slice, the complete
test suite, `git diff --check`, and a staged-file inspection for credentials,
personal data, generated files, and unrelated changes.
