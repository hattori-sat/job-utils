"""Memory and Atlassian HTTP adapters behind the synchronization engine."""

import base64
import json
import os
from abc import ABC, abstractmethod
from typing import Dict, Optional
from urllib import request

from jobutils.markdown.normalize import (
    adf_to_markdown,
    markdown_to_adf,
    markdown_to_storage,
    storage_to_markdown,
)


class SyncAdapter(ABC):
    """Interface implemented by local test and remote synchronization adapters."""

    @abstractmethod
    def create(self, kind: str, payload: Dict) -> Dict:
        raise NotImplementedError

    @abstractmethod
    def update(self, kind: str, external_id: str, payload: Dict) -> Dict:
        raise NotImplementedError

    @abstractmethod
    def fetch(
        self, kind: str, external_id: str, options: Optional[Dict] = None
    ) -> Dict:
        raise NotImplementedError


class MemoryAdapter(SyncAdapter):
    """Deterministic adapter for tests and dry-run development."""

    def __init__(self):
        """Initialize an isolated in-memory record store."""

        self.records = {}
        self.counter = 0

    def create(self, kind: str, payload: Dict) -> Dict:
        """Create a deterministic record and return its external identity."""

        self.counter += 1
        identifier = "MEM-{}".format(self.counter)
        url = "https://memory.invalid/{}/{}".format(kind, identifier)
        self.records[identifier] = {"kind": kind, "payload": payload, "url": url}
        return {
            "id": identifier,
            "key": identifier if kind == "jira" else None,
            "url": url,
            "version": payload.get("version", 0) + 1 if kind == "confluence" else None,
        }

    def update(self, kind: str, external_id: str, payload: Dict) -> Dict:
        """Replace an existing in-memory payload."""

        if external_id not in self.records:
            raise ValueError("external record does not exist: {}".format(external_id))
        self.records[external_id]["payload"] = payload
        return {
            "id": external_id,
            "key": external_id if kind == "jira" else None,
            "url": self.records[external_id]["url"],
            "version": payload.get("version", 0) + 1 if kind == "confluence" else None,
        }

    def fetch(
        self, kind: str, external_id: str, options: Optional[Dict] = None
    ) -> Dict:
        """Return an in-memory record converted back to Markdown."""

        record = self.records[external_id]
        payload = record["payload"]
        if kind == "jira":
            body = adf_to_markdown(payload.get("description_adf", {}))
        else:
            body = storage_to_markdown(payload.get("storage_body", ""))
        result = {
            "id": external_id,
            "title": payload.get("title", ""),
            "body_markdown": body,
            "url": record["url"],
        }
        if kind == "jira" and (options or {}).get("progress_comment_field"):
            result["progress_comment"] = payload.get("progress_comment", "")
        if kind == "jira":
            result["issue_type"] = payload.get("issue_type")
            result["parent_key"] = payload.get("parent_key")
        else:
            result["version"] = payload.get("version", 0)
            result["parent_id"] = payload.get("parent_id")
        return result


class AtlassianHttpAdapter(SyncAdapter):
    """Minimal Jira Cloud v3 and Confluence Cloud v2 adapter.

    Credentials are read from environment variables and never serialized into
    a plan or state file.
    """

    def __init__(self, config: Dict[str, str]):
        """Store non-secret endpoint configuration for later requests."""

        self.config = config

    @staticmethod
    def _progress_value(payload: Dict):
        """Render Progress Comment for either Jira text-field shape."""

        value = payload.get("progress_comment", "")
        if payload.get("progress_comment_format") == "adf":
            return markdown_to_adf(value)
        return value

    def _request(
        self,
        base_url: str,
        path: str,
        email_key: str,
        token_key: str,
        method: str,
        body: Dict,
    ) -> Dict:
        """Send one authenticated JSON request using environment credentials."""

        email = os.environ.get(email_key)
        token = os.environ.get(token_key)
        if not email or not token:
            raise RuntimeError("missing Atlassian credentials in environment")
        raw_auth = base64.b64encode((email + ":" + token).encode("utf-8")).decode(
            "ascii"
        )
        data = json.dumps(body).encode("utf-8")
        req = request.Request(base_url.rstrip("/") + path, data=data, method=method)
        req.add_header("Authorization", "Basic " + raw_auth)
        req.add_header("Accept", "application/json")
        req.add_header("Content-Type", "application/json")
        with request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}

    def create(self, kind: str, payload: Dict) -> Dict:
        """Create a Jira issue or Confluence page."""

        if kind == "jira":
            fields = {
                "project": {"key": payload["project"]},
                "summary": payload["title"],
                "issuetype": {"name": payload["issue_type"]},
                "description": payload["description_adf"],
            }
            if payload.get("progress_comment_field") and "progress_comment" in payload:
                fields[payload["progress_comment_field"]] = self._progress_value(payload)
            body = {"fields": fields}
            if payload.get("parent_key"):
                body["fields"]["parent"] = {"key": payload["parent_key"]}
            result = self._request(
                self.config["jira_base_url"],
                "/rest/api/3/issue",
                "JIRA_EMAIL",
                "JIRA_API_TOKEN",
                "POST",
                body,
            )
            return {
                "id": result.get("id"),
                "key": result.get("key"),
                "url": self.config["jira_base_url"].rstrip("/")
                + "/browse/"
                + result.get("key", ""),
            }
        body = {
            "spaceId": payload["space_id"],
            "status": "current",
            "title": payload["title"],
            "parentId": payload.get("parent_id"),
            "body": {"representation": "storage", "value": payload["storage_body"]},
        }
        result = self._request(
            self.config["confluence_base_url"],
            "/wiki/api/v2/pages",
            "CONFLUENCE_EMAIL",
            "CONFLUENCE_API_TOKEN",
            "POST",
            body,
        )
        page_id = str(result.get("id"))
        return {
            "id": page_id,
            "key": None,
            "url": self.config["confluence_base_url"].rstrip("/")
            + "/wiki/spaces/"
            + str(payload["space_key"])
            + "/pages/"
            + page_id,
            "version": result.get("version", {}).get("number", 1),
        }

    def update(self, kind: str, external_id: str, payload: Dict) -> Dict:
        """Update a Jira issue or Confluence page by stable identity."""

        if kind == "jira":
            fields = {
                "summary": payload["title"],
                "description": payload["description_adf"],
            }
            if payload.get("parent_key"):
                fields["parent"] = {"key": payload["parent_key"]}
            if payload.get("progress_comment_field") and "progress_comment" in payload:
                fields[payload["progress_comment_field"]] = self._progress_value(payload)
            body = {"fields": fields}
            result = self._request(
                self.config["jira_base_url"],
                "/rest/api/3/issue/" + external_id,
                "JIRA_EMAIL",
                "JIRA_API_TOKEN",
                "PUT",
                body,
            )
            return {
                "id": external_id,
                "key": payload.get("jira_key", external_id),
                "url": payload.get("jira_url"),
            }
        body = {
            "id": external_id,
            "status": "current",
            "title": payload["title"],
            "parentId": payload.get("parent_id"),
            "body": {"representation": "storage", "value": payload["storage_body"]},
            "version": {"number": payload["version"] + 1},
        }
        self._request(
            self.config["confluence_base_url"],
            "/wiki/api/v2/pages/" + external_id,
            "CONFLUENCE_EMAIL",
            "CONFLUENCE_API_TOKEN",
            "PUT",
            body,
        )
        return {
            "id": external_id,
            "key": None,
            "url": payload.get("confluence_url"),
            "version": payload["version"] + 1,
        }

    def fetch(
        self, kind: str, external_id: str, options: Optional[Dict] = None
    ) -> Dict:
        """Fetch and convert an external item into Markdown-compatible text."""

        if kind == "jira":
            result = self._request(
                self.config["jira_base_url"],
                "/rest/api/3/issue/" + external_id,
                "JIRA_EMAIL",
                "JIRA_API_TOKEN",
                "GET",
                {},
            )
            fields = result.get("fields", {})
            response = {
                "id": external_id,
                "title": fields.get("summary", ""),
                "body_markdown": adf_to_markdown(fields.get("description") or {}),
                "url": self.config["jira_base_url"].rstrip("/")
                + "/browse/"
                + external_id,
            }
            field_id = (options or {}).get("progress_comment_field")
            if field_id:
                progress = fields.get(field_id, "") or ""
                if (options or {}).get("progress_comment_format") == "adf":
                    progress = adf_to_markdown(progress or {})
                response["progress_comment"] = progress
            issue_type = fields.get("issuetype") or {}
            if issue_type.get("name"):
                response["issue_type"] = issue_type["name"]
            parent = fields.get("parent") or {}
            if parent.get("key"):
                response["parent_key"] = parent["key"]
            return response
        result = self._request(
            self.config["confluence_base_url"],
            "/wiki/api/v2/pages/" + external_id + "?body-format=storage",
            "CONFLUENCE_EMAIL",
            "CONFLUENCE_API_TOKEN",
            "GET",
            {},
        )
        body = result.get("body", {}).get("storage", {}).get("value", "")
        return {
            "id": external_id,
            "title": result.get("title", ""),
            "body_markdown": storage_to_markdown(body),
            "url": self.config["confluence_base_url"].rstrip("/")
            + "/wiki/pages/"
            + external_id,
            "version": result.get("version", {}).get("number"),
            "parent_id": result.get("parentId"),
        }
