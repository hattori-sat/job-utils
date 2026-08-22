# Foundation and GTD Specifications Implementation Plan

**Goal:** Establish a compact, sanitized domain model and normative GTD specification for the separate GTD Markdown Repository before implementing Python, Vim, synchronization, and metrics features.

**Architecture:** `job-utils` is the environment and utility repository. The GTD Markdown Repository remains a separate data repository and is operated on by the Python CLI. Research notes remain evidence; `spec/` contains short normative rules; `docs/` contains explanatory design and operating material; `AGENTS.md` and tool-specific instruction files provide repository guidance.

**Tech Stack:** Markdown, YAML front matter, Vimscript compatibility notes, Python CLI design, and Git-managed JSONL event logs.

**Reference material:** `docs/research/gtd-model.md`, `docs/research/task-metrics-use-cases.md`, `docs/research/plan-apply-design.md`, and the established Vim workflow.

## Global Constraints

- The GTD Markdown Repository is separate from `job-utils`.
- `gtd.md` is the GTD index; `docs.md` is the document index.
- `:Gtd` remains the prefix dispatcher; there is no separate `:GtdFocus` command.
- Known prefixes may move between non-Inbox sections; Inbox is an intake area and is not a dispatch destination.
- `focus` is a valid prefix with a maximum of three concurrent items; a fourth is rejected atomically.
- `cal` records scheduled intent and is not counted as waiting time.
- `focus → wait` stops active work and starts waiting; `focus → cal` stops active work and records scheduling.
- Markdown front matter uses English keys and values.
- Research notes are not normative specifications and are not rewritten merely to match later decisions.
- Generated reports belong under `.jobutils/output/` and are Git-ignored.

---

### Task 1: Establish the repository document map

**Files:**
- Create: `CONTEXT.md`
- Create: `docs/requirements/overview.md`
- Create: `docs/design/document-map.md`
- Update: `README.md`
- Create: `docs/agent/project-guidance.md`
- Create: `AGENTS.md`
- Create: `CLAUDE.md`
- Create: `.github/copilot-instructions.md`
- Create: `.kiro/steering/project.md`

**Interfaces:**
- Produces the vocabulary and document locations consumed by all later specifications.
- Agent入口 files contain the same concise guidance and point humans to `README.md` and `docs/agent/project-guidance.md` for operational details.

- [x] **Step 1: Write the domain vocabulary**

  Define only these canonical terms in `CONTEXT.md`: GTD Repository, job-utils Repository, Inbox, Next, Today, Focus, Waiting, Calendar, Someday, Project, Task Markdown, Document Markdown, External Identity, Sync Plan, Sync Apply, Metric Event.

- [x] **Step 2: Write the repository boundary**

  Record that `job-utils` contains code, Vim integration, setup guidance, and AI-tool guidance, while the separate GTD Repository contains `gtd.md`, `docs.md`, task/document Markdown, `.jobutils/`, event logs, taxonomy, and generated ignored output.

- [x] **Step 3: Write the sanitized overview and document map**

  Describe the purpose and where requirements, specifications, design notes, research, operations, agent guidance, and ADRs live. Keep the document focused on repository structure and reader-facing intent.

- [x] **Step 4: Write shared Agent guidance and tool adapters**

  Put concise project rules in `docs/agent/project-guidance.md`. Copy the same sanitized content into `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, and `.kiro/steering/project.md`; do not invent tool-specific behavior beyond the file’s role.

- [x] **Step 5: Verify document hygiene**

  Run:

  ```bash
  rg -n "TODO|TBD" CONTEXT.md docs/requirements docs/design docs/agent AGENTS.md CLAUDE.md .github .kiro
  git diff --check
  ```

  Expected: the created documents are self-contained and `git diff --check` succeeds.

### Task 2: Specify GTD state and dispatch behavior

**Files:**
- Create: `spec/gtd/state-model.md`
- Create: `spec/gtd/dispatch.md`
- Create: `docs/design/gtd-state-graph.md`

**Interfaces:**
- Produces the normative prefix vocabulary and dispatch invariants for the future Vim/Python implementation.
- The state model is a graph, not a single prescribed workflow.

- [x] **Step 1: Define the prefix vocabulary**

  Specify `next`, `today`, `focus`, `wait`, `cal`, `someday`, `project`, and `done`, with the user-facing Japanese review labels separated from English front matter values.

- [x] **Step 2: Define the Inbox boundary**

  Specify that unclassified Inbox items may be clarified into known destinations, but a known item is not dispatched back to Inbox. Unknown prefixes are ignored or rejected according to the existing Vimrc behavior and must not be silently reclassified.

- [x] **Step 3: Define Focus cardinality**

  Specify that up to three `focus` items are valid. Before mutating `gtd.md`, dispatch counts the resulting Focus items; if the result is four or more, it aborts without deleting, appending, or updating linked details and displays `GTD: dispatch failed`.

- [x] **Step 4: Define arbitrary non-Inbox transitions**

  Specify that a prefixed item may move between known non-Inbox destinations, including `focus → next`, `focus → today`, `focus → wait`, `focus → cal`, and `focus → done`. The implementation records the observed transition rather than enforcing a linear workflow.

- [x] **Step 5: Define Calendar and Waiting semantics**

  Specify that `wait` starts waiting-time accounting, while `cal` records scheduled intent and does not add waiting time. A later `cal → today` transition preserves the schedule history and starts the Today execution phase.

- [x] **Step 6: Verify the state graph**

  Check the document against the established Vim scan, bucket, and append behavior and confirm that every existing prefix remains supported after adding `focus`.

### Task 3: Specify task Markdown and event identity

**Files:**
- Create: `spec/gtd/markdown-format.md`
- Create: `spec/gtd/metrics-events.md`
- Create: `docs/design/metrics-event-model.md`

**Interfaces:**
- Produces the stable Markdown and JSONL event contracts used by later CLI, Vim, sync, and reporting work.

- [x] **Step 1: Define the task front matter**

  Use English YAML keys and preserve the useful existing fields while permitting cleanup of indentation and structure. Define stable identity, title, prefix/status, dates, links, tags, impact, and external identities without placing secrets in Markdown.

- [x] **Step 2: Define task body headings**

  Specify the compact task template in this order: Summary, Description, Progress Comment, Background, Objective, Implementation Note, Scope, Deliverables, Acceptance Criteria, Preconditions, Dependencies, Risks, Open Questions, References. Keep Implementation Note local-only for external publishing.

- [x] **Step 3: Define stable identity for unlinked items**

  On the first dispatch of a known non-`done` prefixed item without a link, create one detail file under `gtd_tasks/`, write its stable `gtd_id` into front matter, and replace the gtd.md line with the generated link. Existing links are reused and never receive a second identity. An unlinked `done` item remains invalid until a detail exists, preserving the current Vimrc safety rule.

- [x] **Step 4: Define event records**

  Define append-only JSONL events with UUID, task ID, timestamp, source machine, source command, previous prefix, new prefix, and optional scheduled/work interval fields. Include status changes, focus changes, work start/stop, capture/clarify, publication, sync, error, and conflict events.

- [x] **Step 5: Define yearly event files and cross-period queries**

  Use `.jobutils/metrics/events/YYYY.jsonl` by default. Reports must scan all requested years and support arbitrary date ranges; file partitioning must never limit comparison periods.

- [x] **Step 6: Verify deterministic examples**

  Include examples for `next → today → focus → wait → today → focus → cal → today → done`, ensuring waiting time, scheduled time, active time, and cycle time remain distinguishable.

### Task 4: Prepare follow-on implementation plans

**Files:**
- Create: `docs/superpowers/plans/2026-08-23-gtd-vim.md`
- Create: `docs/superpowers/plans/2026-08-23-sync-and-references.md`
- Create: `docs/superpowers/plans/2026-08-23-metrics-and-reports.md`
- Create: `docs/superpowers/plans/2026-08-23-setup-and-agent-guidance.md`

**Interfaces:**
- Each plan is independently testable and references the specifications created in Tasks 1–3.

- [x] **Step 1: Split the subsystems**

  Keep Vim/GTD dispatch, Python Markdown/Jira/Confluence synchronization, metrics/reporting, and cross-platform setup as separate plans.

- [x] **Step 2: Map implementation files and tests**

  For each plan, list exact files, public CLI/Vim interfaces, fixtures, unit tests, integration tests, and verification commands. Do not use placeholders such as `TBD` or “add appropriate tests.”

- [x] **Step 3: Run a plan coverage review**

  Confirm every requirement in `docs/requirements/overview.md` maps to exactly one follow-on plan and that no plan assumes an undocumented field or transition.

## Self-review checklist

- Research files remain evidence and are not rewritten as specifications.
- Specifications are short, normative, and written for their intended readers.
- Focus is capped at three, not one.
- Inbox is not a valid dispatch destination.
- Calendar is not waiting.
- The established Vim workflow’s whole-file scan and section bucketing remain the behavioral baseline.
- Generated reports are ignored output, not source data.
