# Cross-Platform Setup and Agent Guidance Implementation Plan

## Goal

Provide a small, dependency-light setup and usage surface for Windows, macOS,
and Ubuntu without installing AI skills automatically.

## Scope

- Document supported Vim/Python versions and required capabilities.
- Provide platform-neutral Python module commands and thin shell/PowerShell
  examples where they improve discoverability.
- Provide a configuration template for the separate GTD repository path,
  external endpoints, and a stable machine alias.
- Document the maintained AI skill list and usage snippets without installing
  skills.
- Keep agent guidance synchronized across root and tool-specific files.

## Files and interfaces

- Create `docs/setup/README.md`, `docs/setup/config.example.yaml`, and
  `docs/setup/platform-notes.md`.
- Create `docs/skills/README.md` and `docs/skills/catalog.md`.
- Create `scripts/jobutils` and `scripts/jobutils.ps1` as optional wrappers for
  the Python module entry point.
- Create `tests/test_config.py` and `tests/test_setup_docs.py`.

## Verification

- Validate the configuration example without requiring live Jira or Confluence
  credentials.
- Exercise module commands with a fixture repository on macOS/Linux-compatible
  paths and Windows-style path fixtures.
- Check that setup does not install Vim, Python, Docker, or AI skills.
- Run documentation hygiene, secret scanning, focused tests, and
  `git diff --check`.
