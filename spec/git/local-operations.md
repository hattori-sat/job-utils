# Local Git Operations

The GTD Markdown Repository remains the source repository for personal task
and document data. job-utils provides explicit local Git helpers for saving
changes and for rehearsing a later remote push without contacting GitHub.

## Commands

```text
jobutils git status --repo REPOSITORY
jobutils git commit --repo REPOSITORY --message "MESSAGE"
jobutils git push-mock --repo REPOSITORY
```

`git commit` stages and commits local changes only. Before committing, it
rejects credential-shaped paths such as `.env`, private-key files, PEM files,
and common key-store files. The commit intent is recorded in the repository's
metric event log after this check. It never invokes a remote operation.

`git push-mock` requires a clean working tree and reports the branch, revision,
and illustrative push command. It always returns `performed: false` and does
not create or contact a remote.
