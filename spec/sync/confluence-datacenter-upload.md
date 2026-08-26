# Confluence Data Center upload

The `confluence-datacenter` adapter is a one-way publication boundary from the
separate GTD Markdown Repository to Confluence Data Center. It is intentionally
not used by `sync check`, because Data Center page fetch/import is outside this
initial scope.

## API contract

- Create: `POST /rest/api/content`
- Update: `PUT /rest/api/content/{id}`
- Body representation: Confluence storage format
- Space: `space.key` from `CONFLUENCE_SPACE_KEY` or document front matter
- Parent: `ancestors: [{"id": "..."}]` on create when a parent ID is present
- Version: incremented in the update request

The configured `CONFLUENCE_BASE_URL` is used as-is, including a Data Center
installation context path such as `/confluence`. Authentication uses the
existing `CONFLUENCE_AUTH_TYPE` setting; Data Center installations commonly
use `basic` with `CONFLUENCE_EMAIL` and `CONFLUENCE_API_TOKEN`.

Use:

```text
jobutils sync plan --repo REPOSITORY
jobutils sync apply --repo REPOSITORY --plan PLAN --adapter confluence-datacenter
```

The adapter rejects Jira actions and all fetch/import operations. A successful
apply writes the returned page ID and URL into the document front matter, and
the normal apply workflow can commit and push that Markdown state.

The endpoint and payload shape follow the [Confluence Data Center Content REST
API](https://developer.atlassian.com/server/confluence/rest/v900/api-group-content-resource/).
