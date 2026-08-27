# Atlassian authentication and Jira API version

The Atlassian adapters use Jira REST API v2 for Jira issue reads and writes.
`JIRA_PLATFORM=cloud` selects the Cloud adapter; `JIRA_PLATFORM=datacenter`
selects the Data Center adapter. Confluence continues to use its REST API v2
endpoints or its upload-only Data Center adapter according to its platform
setting.

Authentication is selected independently for Jira and Confluence:

```text
JIRA_AUTH_TYPE=bearer
CONFLUENCE_AUTH_TYPE=bearer
```

`bearer` sends `Authorization: Bearer <token>` and does not require an email
value. `basic` sends the Atlassian email and token as an RFC 7617 Basic
credential. Jira Data Center Basic authentication uses `JIRA_USERNAME` when
provided, falling back to `JIRA_EMAIL` for compatibility. The default is
`bearer`; Basic remains available for existing installations that explicitly
select it.

The Jira v2 adapters send the description as Jira wiki text, not ADF. They
import both Jira wiki text and an ADF object defensively so existing external
records can still be read. Cloud self-assignment sends `assignee.accountId`;
Data Center self-assignment sends `assignee.name`. HTTP errors include the
service, method, endpoint path, status, and a bounded response-body excerpt
without credentials.

The token is read from the ignored job-utils `.env` file through the normal
CLI environment loader. Tokens never enter plans, Markdown front matter,
metric events, or logs.
