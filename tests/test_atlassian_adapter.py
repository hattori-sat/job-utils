import base64
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from jobutils.sync.adapters import AtlassianHttpAdapter


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b'{"ok": true}'


class AtlassianAdapterTests(unittest.TestCase):
    def setUp(self):
        self.adapter = AtlassianHttpAdapter(
            {
                "jira_base_url": "https://example.atlassian.net",
                "confluence_base_url": "https://example.atlassian.net",
            }
        )

    def test_bearer_auth_is_default_and_does_not_require_email(self):
        captured = {}

        def open_request(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return _Response()

        with patch.dict(os.environ, {"JIRA_API_TOKEN": "bearer-token"}, clear=True):
            with patch("jobutils.sync.adapters.request.urlopen", open_request):
                self.adapter._request(
                    "https://example.atlassian.net",
                    "/rest/api/2/myself",
                    "JIRA_EMAIL",
                    "JIRA_API_TOKEN",
                    "GET",
                    {},
                    auth_type_key="JIRA_AUTH_TYPE",
                    service="jira",
                )

        self.assertEqual(
            captured["request"].get_header("Authorization"),
            "Bearer bearer-token",
        )

    def test_basic_auth_remains_available_when_selected(self):
        captured = {}

        def open_request(request, timeout):
            captured["request"] = request
            return _Response()

        with patch.dict(
            os.environ,
            {
                "JIRA_AUTH_TYPE": "basic",
                "JIRA_EMAIL": "user@example.com",
                "JIRA_API_TOKEN": "basic-token",
            },
            clear=True,
        ):
            with patch("jobutils.sync.adapters.request.urlopen", open_request):
                self.adapter._request(
                    "https://example.atlassian.net",
                    "/rest/api/2/myself",
                    "JIRA_EMAIL",
                    "JIRA_API_TOKEN",
                    "GET",
                    {},
                    auth_type_key="JIRA_AUTH_TYPE",
                    service="jira",
                )

        expected = "Basic " + base64.b64encode(
            b"user@example.com:basic-token"
        ).decode("ascii")
        self.assertEqual(captured["request"].get_header("Authorization"), expected)

    def test_http_error_includes_bounded_service_details(self):
        error = HTTPError(
            "https://example.atlassian.net/rest/api/2/issue",
            403,
            "Forbidden",
            {},
            None,
        )
        error.read = lambda: b'{"errorMessages":["permission denied"]}'
        with patch.dict(os.environ, {"JIRA_API_TOKEN": "bearer-token"}, clear=True):
            with patch("jobutils.sync.adapters.request.urlopen", side_effect=error):
                with self.assertRaisesRegex(
                    RuntimeError,
                    r"jira POST /rest/api/2/issue: HTTP 403.*permission denied",
                ):
                    self.adapter._request(
                        "https://example.atlassian.net",
                        "/rest/api/2/issue",
                        "JIRA_EMAIL",
                        "JIRA_API_TOKEN",
                        "POST",
                        {},
                        auth_type_key="JIRA_AUTH_TYPE",
                        service="jira",
                    )

    def test_jira_create_uses_v2_endpoint_and_wiki_description(self):
        payload = {
            "project": "DEMO",
            "title": "Task",
            "issue_type": "Task",
            "description": "h1. Task\n\nDetails\n",
        }
        with patch.object(
            self.adapter,
            "_request",
            return_value={"id": "10001", "key": "DEMO-1"},
        ) as request_mock:
            result = self.adapter.create("jira", payload)

        self.assertEqual(result["key"], "DEMO-1")
        args, kwargs = request_mock.call_args
        self.assertEqual(args[1], "/rest/api/2/issue")
        self.assertEqual(args[5]["fields"]["description"], payload["description"])
        self.assertEqual(kwargs["auth_type_key"], "JIRA_AUTH_TYPE")

    def test_confluence_create_keeps_v2_endpoint_and_uses_service_auth(self):
        payload = {
            "space_id": "space-1",
            "space_key": "DOC",
            "title": "Guide",
            "storage_body": "<p>Guide</p>",
        }
        with patch.object(
            self.adapter,
            "_request",
            return_value={"id": "page-1", "version": {"number": 1}},
        ) as request_mock:
            result = self.adapter.create("confluence", payload)

        self.assertEqual(result["id"], "page-1")
        args, kwargs = request_mock.call_args
        self.assertEqual(args[1], "/wiki/api/v2/pages")
        self.assertEqual(kwargs["auth_type_key"], "CONFLUENCE_AUTH_TYPE")


if __name__ == "__main__":
    unittest.main()
