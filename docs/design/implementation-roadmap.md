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
   - Tables, links, images, code blocks, lists, and explicit supported macros,
     with Markdown round-trip tests for the external representations.
   - Local-only Implementation Notes and preserved conflict markers.

5. **External synchronization**
   - Reviewable JSON plans followed by explicit apply.
   - Jira tasks, stories, and subtasks.
   - Confluence pages, parent relationships, default values, and recursive
     child creation.
   - Pull, local identity rebind, Jira/Confluence parent dependency resolution,
     stale-plan detection, and two-sided conflict handling.
   - External IDs, URLs, and clickable local references in Markdown.
