# Atlassian API Notes

The synchronization adapter targets the current Atlassian Cloud REST APIs and
keeps authentication outside the repositories.

## Jira Cloud

The Jira Cloud REST API v3 issue resource supports creating and editing issues
and subtasks. Jira descriptions and multi-line text fields use Atlassian
Document Format (ADF), while single-line text custom fields use strings.

Source: [Jira Cloud REST API v3 — Issues](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/)

## Confluence Cloud

The Confluence Cloud REST API v2 page resource creates pages with a `spaceId`,
title, optional `parentId`, and a body whose storage representation is HTML-
like Confluence storage content. Page creation is published by default unless
the request specifies another status.

Source: [Confluence Cloud REST API v2 — Page](https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-page/)

## Adapter boundary

The local Markdown normalizer owns the canonical representation and removes
Implementation Notes before building external payloads. The HTTP adapter owns
authentication, endpoint paths, response parsing, and external identifiers.
Tokens are read from the process environment and are never written to plans,
front matter, logs, or reports.
