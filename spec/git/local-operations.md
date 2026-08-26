# Local Git Operations

The GTD Markdown Repository remains the source repository for personal task
and document data. Git operations are owned by the synchronization workflow in
normal use.

When setup starts with a clean GTD Repository, it creates one local setup
commit for the bootstrap changes. This also covers a repository whose README
already has the first commit. When there is no commit yet, the commit includes
the current non-ignored repository contents. Setup never pushes and never
absorbs pre-existing local changes into this commit.

## User-facing synchronization

```text
jobutils sync update --repo REPOSITORY
jobutils sync apply --repo REPOSITORY --plan PLAN --adapter atlassian
jobutils sync check --repo REPOSITORY --adapter atlassian
jobutils sync plan --repo REPOSITORY
```

`sync update` performs a clean-worktree, fast-forward-only update from the
configured Git remote. It never contacts Jira or Confluence. The Vim launcher
runs it before opening the configured GTD repository; `:GtdSyncUpdate` is the
manual recovery entry point.

`sync check` refreshes Git remote-tracking data and current Jira/Confluence
records, then writes an ignored observation. It never pulls, commits, or
pushes. The observation records whether Git is `in_sync`, `remote_ahead`,
`local_ahead`, `diverged`, or `no_remote`; `remote_ahead` and `diverged` block
planning until `sync update` succeeds.

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
