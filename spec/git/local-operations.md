# Local Git Operations

The GTD Markdown Repository remains the source repository for personal task
and document data. job-utils provides explicit local Git helpers for saving
changes and synchronizing committed data to its configured remote.

## Commands

```text
jobutils git status --repo REPOSITORY
jobutils git commit --repo REPOSITORY --message "MESSAGE"
jobutils git push --repo REPOSITORY [--remote origin] [--branch BRANCH]
jobutils git push-mock --repo REPOSITORY
```

`git commit` stages and commits local changes only. Before committing, it
rejects credential-shaped paths such as `.env`, private-key files, PEM files,
and common key-store files. The commit intent is recorded in the repository's
metric event log after this check. It never invokes a remote operation.

`git push` requires a clean working tree and an existing configured remote. It
pushes the selected branch using Git's configured credential helper or SSH
agent. It never invokes a shell, embeds credentials, or force-pushes. A failed
push leaves the local commit in place so the user can retry `git push`.

`git push-mock` remains a deterministic dry run for tests and review. It
requires a clean working tree, reports the branch and revision, always returns
`performed: false`, and does not create or contact a remote.

`sync apply --adapter atlassian` performs the external Jira/Confluence apply,
commits the resulting Markdown and `.jobutils` synchronization state, and
pushes that commit. It stops before the external request if the working tree
is already dirty. Use `--no-git-sync` only when the local commit and push are
being handled separately.
