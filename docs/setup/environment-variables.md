# Environment variables

The setup script creates `.env` in the job-utils checkout from
`.env.example`. It asks for missing values and preserves values already
present. Token prompts are hidden. `.env` is ignored by Git; do not put these
values in Markdown front matter, metric events, setup logs, or reports.

| Variable | Meaning |
| --- | --- |
| `JIRA_PLATFORM` | Jira deployment: `cloud` (default) or `datacenter`. |
| `JIRA_BASE_URL` | Atlassian base URL, for example `https://example.atlassian.net`. |
| `JIRA_AUTH_TYPE` | `bearer` (default) or `basic`; selects the Jira Authorization header. |
| `JIRA_EMAIL` | Atlassian account email used only when `JIRA_AUTH_TYPE=basic`. |
| `JIRA_USERNAME` | Jira Data Center username used for Basic authentication when set, and as the compatibility identity for self-assignment. |
| `JIRA_API_TOKEN` | Jira Bearer token by default, or Basic API token when `JIRA_AUTH_TYPE=basic`. Keep it secret. |
| `JIRA_PROJECT` | Default Jira project key for the local workspace. |
| `JIRA_ISSUE_TYPE` | Default issue type, normally `Task` or `Story`. |
| `JIRA_ASSIGN_TO_SELF` | `true` by default; assigns newly created Jira issues to the authenticated user. Set `false` to leave new issues unassigned. |
| `JIRA_SUMMARY_FIELD` | Jira Summary field ID; defaults to the standard system field `summary`. |
| `JIRA_DESCRIPTION_FIELD` | Jira Description field ID; defaults to the standard system field `description`. |
| `JIRA_PROGRESS_COMMENT_FIELD` | Optional Jira custom-field ID for Progress Comment. |
| `JIRA_PROGRESS_COMMENT_FORMAT` | `text` for a text field or `adf` for an Atlassian document field. |
| `CONFLUENCE_PLATFORM` | Confluence deployment: `cloud` (default) or `datacenter`. Setup asks this on the first configuration run. |
| `CONFLUENCE_BASE_URL` | Atlassian base URL for Confluence. For Data Center, include the installation context path when needed, such as `https://confluence.example.com/confluence`. |
| `CONFLUENCE_AUTH_TYPE` | `bearer` (default) or `basic`; selects the Confluence Authorization header. |
| `CONFLUENCE_EMAIL` | Atlassian account email used only when `CONFLUENCE_AUTH_TYPE=basic`. |
| `CONFLUENCE_API_TOKEN` | Confluence Bearer token by default, or Basic API token when `CONFLUENCE_AUTH_TYPE=basic`. Keep it secret. |
| `CONFLUENCE_SPACE_ID` | Default Confluence space ID. |
| `CONFLUENCE_SPACE_KEY` | Default Confluence space key for the local workspace. |
| `CONFLUENCE_PARENT_ID` | Default parent page ID for new document pages. |

When `JIRA_ASSIGN_TO_SELF=true`, Cloud creates first read the authenticated
user's `accountId` and Data Center creates first read the authenticated user's
`name` from `/rest/api/2/myself`; the matching identity is included only on
create. Existing issues are not reassigned during ordinary Markdown updates.
Set the variable to `false` when new issues should use Jira's default assignee.

The lower-level CLI reads configuration from the process environment. The
normal setup wrappers run from the configured checkout and load `.env` for
the operations that need it. For manual Python work, load it in the current
shell or use `jobutils-activate`; never commit the file.

Jira field IDs use the environment defaults unless a task sets
`jira_summary_field`, `jira_description_field`, or
`jira_progress_comment_field` in its front matter. The standard Jira system
field IDs are `summary` and `description`. During setup, Jira's field catalog
is queried to confirm and materialize the Summary and Description IDs. The
Progress Comment ID remains manual and is never inferred.

Non-secret project, space, and parent defaults can be overridden by Markdown
front matter. Tokens are never copied into front matter or synchronization
plans.

Jira synchronization uses REST API v2 and sends Bearer authentication by
default. Jira v2 receives wiki-text descriptions rather than Jira v3 ADF. For
Jira Data Center, set `JIRA_PLATFORM=datacenter`; Basic authentication uses
`JIRA_USERNAME` when present, and self-assignment sends the Data Center
`name` field rather than the Cloud `accountId` field.
