# Confluence Data Center upload

The `confluence-datacenter` adapter is a one-way publication boundary from the
separate GTD Markdown Repository to Confluence Data Center. It is intentionally
used by `sync check` only as an upload-only boundary: Data Center pages are
reported as `upload_only` without a page GET or import attempt. Jira Cloud
items continue through the normal Jira adapter.

## API contract

- Create: `POST /rest/api/content`
- Update: `PUT /rest/api/content/{id}`
- Body representation: Confluence storage format
- Space: `space.key` from `CONFLUENCE_SPACE_KEY` or document front matter
- Parent: `ancestors: [{"id": "..."}]` on create when a parent ID is present
- Version: incremented in the update request

Set `CONFLUENCE_PLATFORM=datacenter`. The configured `CONFLUENCE_BASE_URL` is
used as-is, including a Data Center installation context path such as
`/confluence`. Authentication uses the existing `CONFLUENCE_AUTH_TYPE` setting;
Data Center installations commonly use `basic` with `CONFLUENCE_EMAIL` and
`CONFLUENCE_API_TOKEN`.

With this profile, normal apply routes Jira actions to the Jira Cloud adapter
and Confluence actions to this upload-only adapter. The explicit
`confluence-datacenter` adapter remains available for document-only plans.

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
