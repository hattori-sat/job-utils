# Environment variables

The setup script creates `.env` in the job-utils checkout from
`.env.example`. It asks for missing values and preserves values already
present. Token prompts are hidden. `.env` is ignored by Git; do not put these
values in Markdown front matter, metric events, setup logs, or reports.

| Variable | Meaning |
| --- | --- |
| `JIRA_BASE_URL` | Atlassian base URL, for example `https://example.atlassian.net`. |
| `JIRA_AUTH_TYPE` | `bearer` (default) or `basic`; selects the Jira Authorization header. |
| `JIRA_EMAIL` | Atlassian account email used only when `JIRA_AUTH_TYPE=basic`. |
| `JIRA_API_TOKEN` | Jira Bearer token by default, or Basic API token when `JIRA_AUTH_TYPE=basic`. Keep it secret. |
| `JIRA_PROJECT` | Default Jira project key for the local workspace. |
| `JIRA_ISSUE_TYPE` | Default issue type, normally `Task` or `Story`. |
| `JIRA_PROGRESS_COMMENT_FIELD` | Optional Jira custom-field ID for Progress Comment. |
| `JIRA_PROGRESS_COMMENT_FORMAT` | `text` for a text field or `adf` for an Atlassian document field. |
| `CONFLUENCE_BASE_URL` | Atlassian base URL for Confluence. |
| `CONFLUENCE_AUTH_TYPE` | `bearer` (default) or `basic`; selects the Confluence Authorization header. |
| `CONFLUENCE_EMAIL` | Atlassian account email used only when `CONFLUENCE_AUTH_TYPE=basic`. |
| `CONFLUENCE_API_TOKEN` | Confluence Bearer token by default, or Basic API token when `CONFLUENCE_AUTH_TYPE=basic`. Keep it secret. |
| `CONFLUENCE_SPACE_ID` | Default Confluence space ID. |
| `CONFLUENCE_SPACE_KEY` | Default Confluence space key for the local workspace. |
| `CONFLUENCE_PARENT_ID` | Default parent page ID for new document pages. |

The lower-level CLI reads configuration from the process environment. The
normal setup wrappers run from the configured checkout and load `.env` for
the operations that need it. For manual Python work, load it in the current
shell or use `jobutils-activate`; never commit the file.

Non-secret project, space, and parent defaults can be overridden by Markdown
front matter. Tokens are never copied into front matter or synchronization
plans.

Jira synchronization uses REST API v2 and sends Bearer authentication by
default. Jira v2 receives wiki-text descriptions rather than Jira v3 ADF.
