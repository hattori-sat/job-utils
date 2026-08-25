# Local Git Operations

The GTD Markdown Repository remains the source repository for personal task
and document data. Git operations are owned by the synchronization workflow in
normal use.

## User-facing synchronization

```text
jobutils sync apply --repo REPOSITORY --plan PLAN --adapter atlassian
jobutils sync pull --repo REPOSITORY --adapter atlassian
```

`sync apply` automatically commits pending local changes after the normal
credential-path checks, performs the external Jira/Confluence apply, commits
the resulting Markdown and `.jobutils` synchronization state, and pushes the
commits.

`sync pull` fast-forwards the local branch first, imports external changes,
then commits and pushes any resulting local changes. A dirty worktree or a
non-fast-forward branch stops the operation before external requests.

## Internal boundary

The Python `gitops` module retains direct `commit`, `pull`, `push`, and
`push_mock` functions for tests and controlled recovery. They use Git without a
shell, delegate authentication to Git, reject credential-shaped files before a
commit, never force-push, and redact credential-shaped URLs from errors. These
functions are not exposed as normal CLI commands.
