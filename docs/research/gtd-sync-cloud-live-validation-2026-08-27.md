# GTD Sync Cloud live validation — 2026-08-27

## Scope

This note records live validation of `job-utils` against Jira Cloud and
Confluence Cloud using the separate Markdown repository at
`/Users/hattori/work/gtd-htr`. Data Center was not used.

The live fixtures were created under the configured Confluence parent and in
the configured Jira project. Existing Confluence pages and existing Jira
issues were not deleted. The test-only Confluence deletion scenario created
two temporary child pages and deleted those two pages only.

## Authentication finding

The initial configuration had no explicit `JIRA_AUTH_TYPE` or
`CONFLUENCE_AUTH_TYPE`, so the implementation selected Bearer authentication.
Read-only live checks returned Jira HTTP 403 and Confluence HTTP 404.

The same checks with Basic authentication succeeded for Jira current-user
lookup, the Confluence space, and the configured Confluence parent page. The
local ignored `.env` was updated with `JIRA_AUTH_TYPE=basic` and
`CONFLUENCE_AUTH_TYPE=basic`; secret values were not changed or displayed.

## Live scenarios

| Scenario | Result |
| --- | --- |
| `main` fast-forwarded from `origin/main` | Passed; local `main` was updated before validation |
| Setup against `gtd-htr` | Passed in an isolated home; normal setup stopped at an unmanaged existing user wrapper without overwriting it |
| Initial Jira and Confluence create | Passed; Jira fixture `LIG-6`, Confluence fixture `211451905` |
| Immediate check after create | Found and fixed a false Confluence drift caused by the generated self-reference |
| Markdown-only Jira and Confluence update | Passed; both were detected as `local_changed` and updated |
| Jira Summary-only Markdown update | Found and fixed a false `external_changed` classification; the Cloud Summary was updated and the final check was `clean` |
| Vim task create, first apply, edit, and second apply | Passed; Jira Cloud test issue `LIG-7` was created, edited, updated, then returned to `clean` |
| External-only Jira and Confluence update | Passed; both were imported from Cloud and returned to `clean` |
| Same-range local/external conflict | Passed; both produced Git-style conflict markers and no Cloud write |
| Manual conflict resolution and re-apply | Passed after using the latest Confluence version; both returned to `clean` |
| Confluence soft line wrapping | Found and fixed false drift by comparing the external representation projection |
| Unicode, ampersands, literal angle brackets, quotes, and code blocks | Passed; Cloud round-trip preserved content and represented literal tags as escaped Markdown |
| Deletion API safety check | Passed; 2 temporary Confluence children created and 2 deleted |
| Dirty Git worktree update guard | Passed; `sync update` stopped with `working tree must be clean before pull` |

## Fixes made

- Confluence sync comparisons now remove the locally generated self-reference
  from the synchronized projection.
- Self-reference matching is limited to the real References section, excludes
  fenced code, and validates the generated page URL shape.
- Confluence local, base, and remote bodies are compared after the same
  Markdown → storage → Markdown projection, preventing false drift from
  soft line wrapping and legacy base snapshots.
- The raw adapter body is retained for import and conflict evidence while the
  projected body is used only for comparison and merge decisions.
- Apply uses the latest Confluence version fetched during preflight for update
  and merge actions, preventing a stale-version HTTP 409 after conflict
  resolution.
- Confluence update and merge actions fetch a current version even when a plan
  has no observation, and fail closed when no version is available.
- Confluence code blocks are sent as CDATA so Cloud does not discard their
  contents, and imported text avoids double-escaping ampersands.
- Jira bodies are compared after the Markdown → Jira wiki → Markdown
  projection, so Cloud's soft line-wrap normalization does not become a false
  `external_changed` state after a Vim edit and re-apply.
- Jira Summary changes are tracked independently from the Description body;
  a local Summary-only edit is published instead of being imported back from
  the unchanged Cloud issue. Existing files without the tracking value use
  their source fingerprint as a backward-compatible fallback.
- Added regression tests for self-reference drift, soft line wrapping,
  latest-version updates, and Jira Summary-only local/external changes.

## Verification evidence

- Full local suite: 221 tests, all passed.
- Live final `sync check`: Jira and Confluence both `clean`, error count 0.
- Live Summary-only Jira update: `check` detected `local_changed`, `plan`
  generated one Jira `update` action, Cloud update returned successfully, and
  the following `check` returned `clean`.
- Live restored-fixture `sync plan`: 0 actions.
- Conflict apply returned nonzero and wrote markers without changing the
  external records; resolution apply returned zero.
- The Vim-created Jira task's second apply returned an `update` action; the
  post-fix check returned `clean` and the following plan contained 0 actions.

## Unknowns and limitations

- The repository has no GTD Sync delete action. Deletion was validated only
  through the direct Confluence Cloud API for newly created test children.
- The separate `gtd-htr` validation repository was committed and pushed to its
  GitHub `main` branch during the final Vim `:GtdSyncApply` validation. The
  `job-utils` feature branch remains separate and is being submitted by the
  current PR.
- The live test fixture resources remain in the permitted test scope so they
  can be inspected or cleaned up deliberately later.
