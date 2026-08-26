# Atlassian authentication and Jira API version

The Atlassian adapter uses Jira Cloud REST API v2 for Jira issue reads and
writes. Confluence continues to use its REST API v2 endpoints.

Authentication is selected independently for Jira and Confluence:

```text
JIRA_AUTH_TYPE=bearer
CONFLUENCE_AUTH_TYPE=bearer
```

`bearer` sends `Authorization: Bearer <token>` and does not require an email
value. `basic` sends the Atlassian email and token as an RFC 7617 Basic
credential. The default is `bearer`; Basic remains available for existing
installations that explicitly select it.

The Jira v2 adapter sends the description as Jira wiki text, not ADF. It
imports both Jira wiki text and an ADF object defensively so existing external
records can still be read. HTTP errors include the service, method, endpoint
path, status, and a bounded response-body excerpt without credentials.

The token is read from the ignored job-utils `.env` file through the normal
CLI environment loader. Tokens never enter plans, Markdown front matter,
metric events, or logs.
