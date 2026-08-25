# Document Map

## Repository layout

```text
job-utils/
├── CONTEXT.md
├── README.md
├── AGENTS.md
├── CLAUDE.md
├── .github/copilot-instructions.md
├── .kiro/steering/project.md
├── src/
├── vim/
├── tests/
├── skills/
├── docs/
│   ├── agent/
│   ├── design/
│   ├── research/
│   ├── requirements/
│   ├── setup/
│   └── skills/
└── spec/
    ├── gtd/
    ├── git/
    ├── server/
    ├── sync/
    └── vim/
```

## Document roles

- `CONTEXT.md`: concise domain vocabulary and term boundaries.
- `docs/research/`: source-backed investigation and evidence.
- `docs/requirements/`: user-visible goals and invariants.
- `docs/design/`: explanatory architecture and data-model notes.
- `spec/`: short normative specifications that implementation must satisfy.
- `docs/agent/`: shared guidance for coding agents and maintainers.
- `docs/setup/`: cross-platform setup and configuration examples.
- `docs/skills/`: maintained AI skill catalog without auto-installation.
- `skills/`: implementation resources for job-utils skill development.
- `spec/git/`: local Git commit and push-simulation behavior.
- `spec/server/`: the localhost-only HTTP interface.

## Separate GTD Repository

```text
gtd-repository/
├── gtd.md
├── docs.md
├── gtd_tasks/
├── documents/
│   └── <document>/<child>.md  # recursive document pages
└── .jobutils/
    ├── metrics/events/
    ├── output/
    ├── sync/
    └── setup/
```

The GTD Repository is an input and data location for job-utils. It is not
embedded in this repository.
