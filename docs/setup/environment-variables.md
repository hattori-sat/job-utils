# Environment variables

The setup script creates `.env` in the job-utils checkout from
`.env.example`. It asks for missing values and preserves values already
present. Token prompts are hidden. `.env` is ignored by Git; do not put these
values in Markdown front matter, metric events, setup logs, or reports.

| Variable | Meaning |
| --- | --- |
| `JIRA_BASE_URL` | Atlassian base URL, for example `https://example.atlassian.net`. |
| `JIRA_EMAIL` | Atlassian account email used for API authentication. |
| `JIRA_API_TOKEN` | Jira API token. Keep it secret. |
| `JIRA_PROJECT` | Default Jira project key for the local workspace. |
| `JIRA_ISSUE_TYPE` | Default issue type, normally `Task` or `Story`. |
| `JIRA_PROGRESS_COMMENT_FIELD` | Optional Jira custom-field ID for Progress Comment. |
| `JIRA_PROGRESS_COMMENT_FORMAT` | `text` for a text field or `adf` for an Atlassian document field. |
| `CONFLUENCE_BASE_URL` | Atlassian base URL for Confluence. |
| `CONFLUENCE_EMAIL` | Atlassian account email used for API authentication. |
| `CONFLUENCE_API_TOKEN` | Confluence API token. Keep it secret. |
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
