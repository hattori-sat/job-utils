# job-utils

Cross-platform utilities for a Vim-centered GTD and work-document workflow.

This repository contains the environment, Python utilities, Vim integration,
setup guidance, and project-agent guidance. The actual GTD Markdown data is
kept in a separate repository containing `gtd.md`, `docs.md`, task documents,
document pages, and `.jobutils/` runtime data.

## Documentation

- [Setup guide](docs/setup/README.md)
- [Usage guide](docs/usage/README.md)
- [Requirements](docs/requirements/overview.md)
- [Document map](docs/design/document-map.md)
- [Implementation roadmap](docs/design/implementation-roadmap.md)
- [Research notes](docs/research/)
- [Specifications](spec/)
- [Agent guidance](docs/agent/project-guidance.md)

The setup guide is the user entry point. The normative behavior is maintained
in `spec/`; research notes and design documents explain the decisions behind
it. The separate GTD Repository contains personal Markdown and runtime data.
