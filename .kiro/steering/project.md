# Project Agent Guidance

## Scope

job-utils is the utility and environment repository for a separate GTD
Markdown Repository. Keep those repositories separate in code, documentation,
tests, and examples.

## Working rules

- Read `README.md`, `CONTEXT.md`, the relevant `spec/` files, and the relevant
  research note before changing behavior.
- Keep specifications short and normative. Put investigation and evidence in
  `docs/research/`.
- Preserve the current Vim-centered workflow while moving shared behavior into
  testable Python/domain code.
- Treat `gtd.md` as the task index and `docs.md` as the document index.
- Never dispatch an item back into Inbox.
- Keep Focus at three or fewer items and fail before mutation when a fourth
  would be introduced.
- Keep Calendar and Waiting as distinct concepts.
- Never publish Implementation Notes or secrets.
- Run focused tests and `git diff --check` before committing.
- Inspect staged files for credentials, personal data, generated output, and
  unrelated changes before any push.
- Work on a `codex/*` branch. Never push directly to `main`.

## Documentation hygiene

Research notes are evidence, not requirements. Before committing a
user-facing requirement, specification, design note, or operating guide,
write it as a concise, self-contained document for its intended readers.

## Human entry points

Start with `README.md`. The canonical domain vocabulary is in `CONTEXT.md`;
requirements are in `docs/requirements/`; normative behavior is in `spec/`.
