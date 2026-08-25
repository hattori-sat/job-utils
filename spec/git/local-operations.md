# Local Git Operations

The GTD Markdown Repository remains the source repository for personal task
and document data. Git operations are owned by the synchronization workflow in
normal use.

## User-facing synchronization

```text
jobutils sync apply --repo REPOSITORY --plan PLAN --adapter atlassian
jobutils sync check --repo REPOSITORY --adapter atlassian
jobutils sync plan --repo REPOSITORY
```

`sync check` refreshes Git remote-tracking data and current Jira/Confluence
records, then writes an ignored observation. It never commits or pushes.

`sync plan` turns the observation into publish, import, or conflict actions.
`sync apply` automatically commits pending local changes together with the
resulting Markdown and `.jobutils` synchronization state after all actions
complete, then pushes the one clean commit.

## Internal boundary

The Python `gitops` module retains direct `commit`, `fetch`, `pull`, `push`, and
`push_mock` functions for tests and controlled recovery. They use Git without a
shell, delegate authentication to Git, reject credential-shaped files before a
commit, never force-push, and redact credential-shaped URLs from errors. These
functions are not exposed as normal CLI commands.
