# Markdown Conversion Implementation Plan

**Goal:** Make the supported Markdown authoring model round-trip predictably through Jira ADF and Confluence storage content.

**Architecture:** Keep Markdown as the canonical authoring format. Extend the
existing normalizer with small block and inline renderers for headings,
paragraphs, links, images, lists, tables, code blocks, and the explicit
Confluence macro directive. Use one Jira ADF builder for sync payloads and
paired readers for external content. Keep externalization and
Implementation Note removal at the existing parser boundary.

**Tech Stack:** Python 3.8+ standard library, HTML escaping, Jira ADF JSON,
Confluence storage XML-like markup, `unittest`.

**Spec:** `docs/design/implementation-roadmap.md`,
`spec/sync/plan-apply.md`, `docs/research/atlassian-api.md`

## Global Constraints

- Markdown remains the canonical local representation.
- Implementation Notes never enter Jira or Confluence payloads.
- User text and URLs must be escaped before entering external markup.
- Unsupported Confluence macros remain explicit directives and are not
  guessed from arbitrary HTML.
- The implementation uses only Python standard-library facilities.
- Jira and Confluence conversion tests use local fixtures and do not call live
  services.

---

### Task 1: Render Markdown blocks and inline references for Confluence

**Files:**
- Modify: `src/jobutils/markdown/normalize.py`
- Test: `tests/test_markdown_conversion.py`

**Interfaces:**
- `markdown_to_storage(body: str) -> str` renders grouped paragraphs,
  headings, unordered/ordered lists, pipe tables, fenced code, links, images,
  and `:::confluence-macro name="..."` blocks.
- Existing `externalize_references()` remains responsible for replacing
  publishable local targets before rendering.

- [x] Write failing tests for links, images, grouped lists, tables, and macro
  bodies, asserting escaped text and URLs.
- [x] Run the focused conversion tests and confirm the new cases fail.
- [x] Add small inline and block helpers inside the normalizer without adding
  third-party dependencies.
- [x] Render table header rows as `<th>`, body rows as `<td>`, and group list
  items into one `<ul>` or `<ol>` element instead of one element per item.
- [x] Render links as escaped `<a href>` elements and published images as
  Confluence `<ac:image>` elements; keep private image targets out of payloads.
- [x] Render macro directives with escaped macro names and their public body.
- [x] Run the focused tests and confirm they pass.
- [x] Commit as `feat: complete markdown external conversion`.

### Task 2: Parse Confluence storage content back to Markdown

**Files:**
- Modify: `src/jobutils/markdown/normalize.py`
- Test: `tests/test_markdown_conversion.py`

**Interfaces:**
- `storage_to_markdown(storage: str) -> str` converts supported Confluence
  headings, paragraphs, links, images, lists, tables, code blocks, and
  structured macro blocks into canonical Markdown.

- [x] Write failing tests for storage headings, links, images, lists, tables,
  code, and the supported macro directive.
- [x] Run the focused tests and confirm the new cases fail.
- [x] Parse only the supported storage subset with `html.parser` so text and
  attributes are decoded safely and arbitrary tags do not become Markdown.
- [x] Preserve macro names and public macro body content in the explicit
  `:::confluence-macro` form.
- [x] Apply `canonical_body()` to stable line endings and final newlines.
- [x] Run the focused tests and confirm they pass.
- [x] Commit as `feat: complete markdown external conversion`.

### Task 3: Use structured Jira ADF for task descriptions

**Files:**
- Modify: `src/jobutils/markdown/normalize.py`
- Modify: `src/jobutils/sync/engine.py`
- Test: `tests/test_markdown_conversion.py`
- Test: `tests/test_sync.py`

**Interfaces:**
- Add `markdown_to_adf(body: str) -> Dict` for headings, paragraphs, links,
  unordered/ordered lists, and fenced code blocks.
- Extend `adf_to_markdown(document: Dict) -> str` for those same ADF blocks.
- `_payload()` uses `markdown_to_adf(document.public_body)` for Jira
  descriptions.

- [x] Write failing tests for Markdown-to-ADF block structure, inline links,
  and ADF-to-Markdown list/code conversion.
- [x] Run the focused tests and confirm the new cases fail.
- [x] Implement deterministic ADF builders with stable block ordering and
  escaped/typed inline nodes.
- [x] Switch Jira payload creation to the shared builder while preserving the
  Progress Comment field behavior.
- [x] Run sync and focused conversion tests and confirm they pass.
- [x] Commit as `feat: complete markdown external conversion`.

### Task 4: Document the supported conversion subset and finish the PR

**Files:**
- Modify: `docs/setup/README.md`
- Modify: `spec/sync/plan-apply.md`
- Modify: `docs/design/implementation-roadmap.md`
- Test: `tests/test_markdown_conversion.py`

- [x] Document the Markdown conversion subset, macro directive syntax, and
  private-reference behavior for users.
- [x] Add an end-to-end fixture test that plans a document and task while
  asserting Implementation Notes and private paths are absent from both
  external payload types.
- [ ] Run the complete test suite and `git diff --check`.
- [ ] Inspect the public diff for credentials, real Atlassian identifiers,
  local paths, and unnecessary private context.
- [ ] Request code review and resolve Critical/Important findings.
- [ ] Push only `codex/pr-markdown-conversion` and open one PR against `main`.
  Do not merge it.
