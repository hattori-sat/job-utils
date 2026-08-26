"""Memory and Atlassian HTTP adapters behind the synchronization engine."""

import base64
import json
import os
from abc import ABC, abstractmethod
from typing import Dict, Optional
from urllib.error import HTTPError
from urllib import request

from jobutils.markdown.normalize import (
    adf_to_markdown,
    jira_wiki_to_markdown,
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
            options = options or {}
            summary_field = options.get("summary_field") or payload.get(
                "summary_field"
            ) or "summary"
            description_field = options.get("description_field") or payload.get(
                "description_field"
            ) or "description"
            title = payload.get(summary_field)
            if title is None:
                title = payload.get("title", "")
            description = payload.get(description_field)
            if description is None:
                description = payload.get("description", "")
            if isinstance(description, dict):
                body = adf_to_markdown(description)
            else:
                body = jira_wiki_to_markdown(str(description))
        else:
            body = storage_to_markdown(payload.get("storage_body", ""))
        result = {
            "id": external_id,
            "title": title if kind == "jira" else payload.get("title", ""),
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
    """Minimal Jira Cloud v2 and Confluence Cloud v2 adapter.

    Credentials are read from environment variables and never serialized into
    a plan or state file.
    """

    def __init__(self, config: Dict[str, str]):
        """Store non-secret endpoint configuration for later requests."""

        self.config = config
        self._jira_current_user_account_id = None

    def _jira_current_user_account_id_value(self) -> str:
        """Resolve and cache the authenticated Jira Cloud user's account ID."""

        if self._jira_current_user_account_id is None:
            result = self._request(
                self.config["jira_base_url"],
                "/rest/api/2/myself",
                "JIRA_EMAIL",
                "JIRA_API_TOKEN",
                "GET",
                {},
                auth_type_key="JIRA_AUTH_TYPE",
                service="jira",
            )
            account_id = result.get("accountId") if isinstance(result, dict) else None
            if not isinstance(account_id, str) or not account_id.strip():
                raise RuntimeError("jira current user response did not include accountId")
            self._jira_current_user_account_id = account_id
        return self._jira_current_user_account_id

    @staticmethod
    def _assign_to_self_enabled(payload: Dict) -> bool:
        """Interpret the non-secret create payload switch safely."""

        value = payload.get("assign_to_self", False)
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)

    @staticmethod
    def _progress_value(payload: Dict):
        """Render Progress Comment for either Jira text-field shape."""

        value = payload.get("progress_comment", "")
        if payload.get("progress_comment_format") == "adf":
            return markdown_to_adf(value)
        return value

    @staticmethod
    def _jira_field(fields: Dict, field_id: str, standard_id: str):
        """Read a configured Jira field with compatibility for standard keys."""

        value = fields.get(field_id)
        if value is None and field_id != standard_id:
            value = fields.get(standard_id)
        return value

    def _request(
        self,
        base_url: str,
        path: str,
        email_key: str,
        token_key: str,
        method: str,
        body: Dict,
        auth_type_key: str = "",
        service: str = "atlassian",
    ) -> Dict:
        """Send one authenticated JSON request using environment credentials."""

        token = os.environ.get(token_key)
        auth_type = (os.environ.get(auth_type_key) or "bearer").strip().lower()
        if not token:
            raise RuntimeError("missing {} token in environment".format(service))
        data = json.dumps(body).encode("utf-8")
        req = request.Request(base_url.rstrip("/") + path, data=data, method=method)
        if auth_type == "bearer":
            req.add_header("Authorization", "Bearer " + token)
        elif auth_type == "basic":
            email = os.environ.get(email_key)
            if not email:
                raise RuntimeError("missing {} email in environment".format(service))
            raw_auth = base64.b64encode((email + ":" + token).encode("utf-8")).decode(
                "ascii"
            )
            req.add_header("Authorization", "Basic " + raw_auth)
        else:
            raise RuntimeError(
                "unsupported {} auth type: {}".format(service, auth_type)
            )
        req.add_header("Accept", "application/json")
        req.add_header("Content-Type", "application/json")
        try:
            with request.urlopen(req, timeout=30) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except HTTPError as error:
            try:
                detail = error.read().decode("utf-8", errors="replace")
            except OSError:
                detail = ""
            detail = detail.replace(token, "<redacted-token>")[:2000]
            message = "{} {} {}: HTTP {}".format(
                service, method, path, error.code
            )
            if detail:
                message += " " + detail
            raise RuntimeError(message) from error

    def create(self, kind: str, payload: Dict) -> Dict:
        """Create a Jira issue or Confluence page."""

        if kind == "jira":
            summary_field = payload.get("summary_field") or "summary"
            description_field = payload.get("description_field") or "description"
            fields = {
                "project": {"key": payload["project"]},
                "issuetype": {"name": payload["issue_type"]},
                summary_field: payload["title"],
                description_field: payload["description"],
            }
            if payload.get("progress_comment_field") and "progress_comment" in payload:
                fields[payload["progress_comment_field"]] = self._progress_value(payload)
            if self._assign_to_self_enabled(payload):
                fields["assignee"] = {
                    "accountId": self._jira_current_user_account_id_value()
                }
            body = {"fields": fields}
            if payload.get("parent_key"):
                body["fields"]["parent"] = {"key": payload["parent_key"]}
            result = self._request(
                self.config["jira_base_url"],
                "/rest/api/2/issue",
                "JIRA_EMAIL",
                "JIRA_API_TOKEN",
                "POST",
                body,
                auth_type_key="JIRA_AUTH_TYPE",
                service="jira",
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
            auth_type_key="CONFLUENCE_AUTH_TYPE",
            service="confluence",
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
            summary_field = payload.get("summary_field") or "summary"
            description_field = payload.get("description_field") or "description"
            fields = {
                summary_field: payload["title"],
                description_field: payload["description"],
            }
            if payload.get("parent_key"):
                fields["parent"] = {"key": payload["parent_key"]}
            if payload.get("progress_comment_field") and "progress_comment" in payload:
                fields[payload["progress_comment_field"]] = self._progress_value(payload)
            body = {"fields": fields}
            result = self._request(
                self.config["jira_base_url"],
                "/rest/api/2/issue/" + external_id,
                "JIRA_EMAIL",
                "JIRA_API_TOKEN",
                "PUT",
                body,
                auth_type_key="JIRA_AUTH_TYPE",
                service="jira",
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
            auth_type_key="CONFLUENCE_AUTH_TYPE",
            service="confluence",
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
                "/rest/api/2/issue/" + external_id,
                "JIRA_EMAIL",
                "JIRA_API_TOKEN",
                "GET",
                {},
                auth_type_key="JIRA_AUTH_TYPE",
                service="jira",
            )
            fields = result.get("fields", {})
            options = options or {}
            summary_field = options.get("summary_field") or "summary"
            description_field = options.get("description_field") or "description"
            description = self._jira_field(
                fields, description_field, "description"
            ) or ""
            if isinstance(description, dict):
                description = adf_to_markdown(description)
            else:
                description = jira_wiki_to_markdown(str(description))
            response = {
                "id": external_id,
                "title": self._jira_field(fields, summary_field, "summary") or "",
                "body_markdown": description,
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
            auth_type_key="CONFLUENCE_AUTH_TYPE",
            service="confluence",
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
