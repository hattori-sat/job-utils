import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from jobutils.cli import _build_atlassian_adapter, main
from jobutils.markdown.normalize import (
    canonical_sync_body,
    markdown_to_storage,
    parse_document,
)
from jobutils.sync.adapters import (
    AtlassianHttpAdapter,
    JiraCloudConfluenceDataCenterAdapter,
    MemoryAdapter,
)
from jobutils.sync.engine import (
    SyncError,
    apply_plan,
    check,
    classify_drift,
    create_plan,
    rebind,
    sync_status,
)
from jobutils.sync.references import externalize_references


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name)
        (self.repo / "documents").mkdir()
        (self.repo / "gtd_tasks").mkdir()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_apply_adapter_uses_configured_confluence_platform(self):
        with patch.dict(
            os.environ,
            {
                "CONFLUENCE_PLATFORM": "datacenter",
                "JIRA_BASE_URL": "https://jira.example",
                "CONFLUENCE_BASE_URL": "https://confluence.example",
            },
            clear=True,
        ):
            adapter = _build_atlassian_adapter("atlassian", for_apply=True)
            check_adapter = _build_atlassian_adapter("atlassian")

        self.assertIsInstance(adapter, JiraCloudConfluenceDataCenterAdapter)
        self.assertIsInstance(check_adapter, AtlassianHttpAdapter)

    def test_invalid_confluence_platform_fails_before_apply(self):
        with patch.dict(os.environ, {"CONFLUENCE_PLATFORM": "server"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "CONFLUENCE_PLATFORM"):
                _build_atlassian_adapter("atlassian", for_apply=True)

    def test_plan_and_apply_exclude_implementation_notes(self):
        path = self.repo / "documents" / "guide.md"
        path.write_text(
            """---
gtd_id: 'doc-1'
kind: 'document'
title: 'Guide'
publish_confluence: 'true'
confluence_space_id: 'space-1'
confluence_space_key: 'DOC'
---

# Guide

Visible content.

# Implementation Note

Private content.
""",
            encoding="utf-8",
        )
        plan = create_plan(self.repo)
        self.assertEqual(len(plan["actions"]), 1)
        self.assertNotIn(
            "Private content", plan["actions"][0]["payload"]["storage_body"]
        )
        adapter = MemoryAdapter()
        result = apply_plan(self.repo, plan, adapter)
        self.assertEqual(len(result), 1)
        updated = path.read_text(encoding="utf-8")
        self.assertIn("confluence_page_id:", updated)
        self.assertIn("confluence_url:", updated)

    def test_cli_sync_apply_commits_and_pushes_requested_git_sync(self):
        repo = Path(self.tempdir.name) / "repo"
        repo.mkdir()
        (repo / "documents").mkdir()
        (repo / "gtd_tasks").mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(
            ["git", "config", "user.email", "local-test"], cwd=repo, check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Job Utils Test"], cwd=repo, check=True
        )
        remote = Path(self.tempdir.name) / "remote.git"
        subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
        subprocess.run(
            ["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True
        )
        document = repo / "documents" / "guide.md"
        document.write_text(
            "---\ngtd_id: doc-1\nkind: document\ntitle: Guide\n"
            "publish_confluence: true\n---\n\n# Guide\n\nContent.\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-qm", "test: seed sync repository"],
            cwd=repo,
            check=True,
        )
        plan_path = Path(self.tempdir.name) / "plan.json"
        plan_path.write_text(
            json.dumps(create_plan(repo)), encoding="utf-8"
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(
                [
                    "sync",
                    "apply",
                    "--repo",
                    str(repo),
                    "--plan",
                    str(plan_path),
                    "--adapter",
                    "memory",
                    "--git-sync",
                ]
            )
        self.assertEqual(result, 0)
        response = json.loads(output.getvalue())
        self.assertTrue(response["git"]["push"]["performed"])
        local_revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip()
        branch = response["git"]["push"]["branch"]
        remote_revision = subprocess.check_output(
            [
                "git",
                "--git-dir",
                str(remote),
                "rev-parse",
                "refs/heads/{}".format(branch),
            ],
            text=True,
        ).strip()
        self.assertEqual(remote_revision, local_revision)

    def test_cli_sync_update_fast_forwards_and_returns_git_result(self):
        repo = Path(self.tempdir.name) / "update-repo"
        repo.mkdir()
        remote = Path(self.tempdir.name) / "update-remote.git"
        subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "config", "user.email", "local-test"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Job Utils Test"], cwd=repo, check=True)
        subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True)
        (repo / "gtd.md").write_text("# GTD\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "test: seed update repository"], cwd=repo, check=True)
        subprocess.run(["git", "push", "-q", "origin", "HEAD"], cwd=repo, check=True)

        peer = Path(self.tempdir.name) / "update-peer"
        subprocess.run(["git", "clone", "-q", str(remote), str(peer)], check=True)
        subprocess.run(["git", "config", "user.email", "peer@example.invalid"], cwd=peer, check=True)
        subprocess.run(["git", "config", "user.name", "Peer Test"], cwd=peer, check=True)
        (peer / "remote.md").write_text("remote\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=peer, check=True)
        subprocess.run(["git", "commit", "-qm", "test: add remote file"], cwd=peer, check=True)
        subprocess.run(["git", "push", "-q", "origin", "HEAD"], cwd=peer, check=True)

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(["sync", "update", "--repo", str(repo)])

        self.assertEqual(result, 0)
        response = json.loads(output.getvalue())
        self.assertTrue(response["git"]["performed"])
        self.assertTrue((repo / "remote.md").is_file())

    def test_cli_sync_update_allows_an_empty_remote(self):
        repo = Path(self.tempdir.name) / "empty-remote-repo"
        repo.mkdir()
        remote = Path(self.tempdir.name) / "empty-remote.git"
        subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "config", "user.email", "local-test"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Job Utils Test"], cwd=repo, check=True)
        subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True)
        (repo / "gtd.md").write_text("# GTD\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "test: seed empty remote repository"], cwd=repo, check=True)

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(["sync", "update", "--repo", str(repo)])

        self.assertEqual(result, 0)
        response = json.loads(output.getvalue())
        self.assertEqual(response["git"]["state"], "no_remote")
        self.assertTrue(response["git"]["skipped"])

    def test_cli_sync_apply_rejects_remote_ahead_before_external_apply(self):
        repo = Path(self.tempdir.name) / "stale-apply-repo"
        repo.mkdir()
        remote = Path(self.tempdir.name) / "stale-apply-remote.git"
        subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "config", "user.email", "local-test"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Job Utils Test"], cwd=repo, check=True)
        subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True)
        document = repo / "documents"
        document.mkdir()
        path = document / "guide.md"
        path.write_text(
            "---\nkind: document\ntitle: Guide\npublish_confluence: true\n---\n\n# Guide\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "test: seed stale apply repository"], cwd=repo, check=True)
        subprocess.run(["git", "push", "-q", "origin", "HEAD"], cwd=repo, check=True)
        plan_path = Path(self.tempdir.name) / "stale-apply-plan.json"
        plan_path.write_text(json.dumps(create_plan(repo)), encoding="utf-8")

        peer = Path(self.tempdir.name) / "stale-apply-peer"
        subprocess.run(["git", "clone", "-q", str(remote), str(peer)], check=True)
        subprocess.run(["git", "config", "user.email", "peer@example.invalid"], cwd=peer, check=True)
        subprocess.run(["git", "config", "user.name", "Peer Test"], cwd=peer, check=True)
        (peer / "peer.md").write_text("peer\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=peer, check=True)
        subprocess.run(["git", "commit", "-qm", "test: advance remote before apply"], cwd=peer, check=True)
        subprocess.run(["git", "push", "-q", "origin", "HEAD"], cwd=peer, check=True)

        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            result = main(
                [
                    "sync",
                    "apply",
                    "--repo",
                    str(repo),
                    "--plan",
                    str(plan_path),
                    "--adapter",
                    "memory",
                    "--git-sync",
                ]
            )

        self.assertEqual(result, 1)
        self.assertIn("remote_ahead", errors.getvalue())
        self.assertNotIn("confluence_page_id:", path.read_text(encoding="utf-8"))

    def test_cli_sync_apply_commits_dirty_worktree_once_after_external_apply(self):
        repo = Path(self.tempdir.name) / "repo"
        repo.mkdir()
        (repo / "documents").mkdir()
        (repo / "gtd_tasks").mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(
            ["git", "config", "user.email", "local-test"], cwd=repo, check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Job Utils Test"], cwd=repo, check=True
        )
        remote = Path(self.tempdir.name) / "remote.git"
        subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
        subprocess.run(
            ["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True
        )
        document = repo / "documents" / "guide.md"
        document.write_text(
            "---\ngtd_id: doc-1\nkind: document\ntitle: Guide\n"
            "publish_confluence: true\n---\n\n# Guide\n\nInitial.\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-qm", "test: seed sync repository"],
            cwd=repo,
            check=True,
        )
        document.write_text(
            document.read_text(encoding="utf-8").replace("Initial.", "Updated."),
            encoding="utf-8",
        )
        plan_path = Path(self.tempdir.name) / "plan.json"
        plan_path.write_text(json.dumps(create_plan(repo)), encoding="utf-8")

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(
                [
                    "sync",
                    "apply",
                    "--repo",
                    str(repo),
                    "--plan",
                    str(plan_path),
                    "--adapter",
                    "memory",
                    "--git-sync",
                ]
            )

        self.assertEqual(result, 0)
        response = json.loads(output.getvalue())
        self.assertIsNotNone(response["git"]["commit"])
        self.assertNotIn("pre_apply_commit", response["git"])
        self.assertTrue(response["git"]["push"]["performed"])
        self.assertEqual(
            subprocess.check_output(
                ["git", "rev-list", "--count", "HEAD"], cwd=repo, text=True
            ).strip(),
            "2",
        )
        self.assertEqual(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=repo, text=True
            ),
            "",
        )

    def test_plan_skips_unmanaged_markdown_without_front_matter(self):
        (self.repo / "documents" / "notes.md").write_text(
            "# Local scratch\n\nThis is not a managed publication.\n",
            encoding="utf-8",
        )

        plan = create_plan(self.repo)

        self.assertEqual(plan["actions"], [])

    def test_plan_rejects_cross_domain_publication(self):
        task = self.repo / "gtd_tasks" / "task.md"
        task.write_text(
            "---\nkind: task\npublish_confluence: true\n---\n\n# Summary\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(SyncError, "only to Jira"):
            create_plan(self.repo)

        task.write_text(
            "---\nkind: task\npublish_jira: true\n---\n\n# Summary\n",
            encoding="utf-8",
        )
        document = self.repo / "documents" / "guide.md"
        document.write_text(
            "---\nkind: document\npublish_jira: true\n---\n\n# Guide\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(SyncError, "only to Confluence"):
            create_plan(self.repo)

    def test_apply_materializes_resolved_defaults(self):
        task = self.repo / "gtd_tasks" / "task.md"
        task.write_text(
            "---\ngtd_id: task-1\nkind: task\ntitle: Task\n"
            "publish_jira: true\n---\n\n# Summary\n",
            encoding="utf-8",
        )
        document = self.repo / "documents" / "guide.md"
        document.write_text(
            "---\ngtd_id: doc-1\nkind: document\ntitle: Guide\n"
            "publish_confluence: true\n---\n\n# Guide\n",
            encoding="utf-8",
        )
        defaults = {
            "JIRA_PROJECT": "LCL",
            "JIRA_ISSUE_TYPE": "Story",
            "JIRA_PROGRESS_COMMENT_FIELD": "customfield_progress",
            "CONFLUENCE_SPACE_ID": "space-local",
            "CONFLUENCE_SPACE_KEY": "DOCS",
            "CONFLUENCE_PARENT_ID": "parent-local",
        }
        with patch.dict(os.environ, defaults, clear=False):
            apply_plan(self.repo, create_plan(self.repo), MemoryAdapter())

        task_text = task.read_text(encoding="utf-8")
        document_text = document.read_text(encoding="utf-8")
        self.assertIn("jira_project: 'LCL'", task_text)
        self.assertIn("jira_issue_type: 'Story'", task_text)
        self.assertIn("jira_summary_field: 'summary'", task_text)
        self.assertIn("jira_description_field: 'description'", task_text)
        self.assertIn("jira_progress_comment_field: 'customfield_progress'", task_text)
        self.assertIn("confluence_space_id: 'space-local'", document_text)
        self.assertIn("confluence_space_key: 'DOCS'", document_text)
        self.assertIn("confluence_parent_id: 'parent-local'", document_text)

    def test_jira_plan_resolves_standard_field_ids_and_front_matter_overrides(self):
        task = self.repo / "gtd_tasks" / "task.md"
        task.write_text(
            "---\ngtd_id: task-1\nkind: task\ntitle: Task\n"
            "publish_jira: true\n---\n\n# Summary\n",
            encoding="utf-8",
        )
        with patch.dict(
            os.environ,
            {
                "JIRA_PROJECT": "LCL",
                "JIRA_SUMMARY_FIELD": "summary",
                "JIRA_DESCRIPTION_FIELD": "description",
            },
            clear=False,
        ):
            payload = create_plan(self.repo)["actions"][0]["payload"]
        self.assertEqual(payload["summary_field"], "summary")
        self.assertEqual(payload["description_field"], "description")

        task.write_text(
            "---\ngtd_id: task-1\nkind: task\ntitle: Task\n"
            "publish_jira: true\n"
            "jira_summary_field: customfield_summary\n"
            "jira_description_field: customfield_description\n"
            "---\n\n# Summary\n",
            encoding="utf-8",
        )
        with patch.dict(
            os.environ,
            {
                "JIRA_SUMMARY_FIELD": "summary",
                "JIRA_DESCRIPTION_FIELD": "description",
            },
            clear=False,
        ):
            payload = create_plan(self.repo)["actions"][0]["payload"]
        self.assertEqual(payload["summary_field"], "customfield_summary")
        self.assertEqual(payload["description_field"], "customfield_description")

    def test_applied_unchanged_item_is_not_pending_again(self):
        path = self.repo / "documents" / "guide.md"
        path.write_text(
            "---\nkind: document\ntitle: Guide\npublish_confluence: true\n---\n\n# Guide\n",
            encoding="utf-8",
        )
        adapter = MemoryAdapter()
        apply_plan(self.repo, create_plan(self.repo), adapter)

        self.assertEqual(create_plan(self.repo)["actions"], [])

    def test_apply_records_success_and_failure_events(self):
        path = self.repo / "documents" / "guide.md"
        path.write_text(
            "---\ngtd_id: doc-1\nkind: document\npublish_confluence: true\n---\n\n# Guide\n",
            encoding="utf-8",
        )
        apply_plan(self.repo, create_plan(self.repo), MemoryAdapter())
        events = list((self.repo / ".jobutils/metrics/events").glob("*.jsonl"))
        self.assertTrue(
            any('"event_type": "sync_applied"' in item.read_text() for item in events)
        )

        failing = self.repo / "documents" / "failing.md"
        failing.write_text(
            "---\ngtd_id: doc-2\nkind: document\npublish_confluence: true\n---\n\n# Failing\n",
            encoding="utf-8",
        )

        class FailingAdapter(MemoryAdapter):
            def create(self, kind, payload):
                raise RuntimeError("simulated failure")

        with self.assertRaises(SyncError):
            apply_plan(self.repo, create_plan(self.repo), FailingAdapter())
        self.assertNotIn("confluence_page_id:", failing.read_text(encoding="utf-8"))
        events = list((self.repo / ".jobutils/metrics/events").glob("*.jsonl"))
        self.assertTrue(
            any('"event_type": "sync_error"' in item.read_text() for item in events)
        )

    def test_apply_imports_remote_title_and_progress_comment(self):
        path = self.repo / "gtd_tasks" / "task.md"
        path.write_text(
            "---\ngtd_id: task-1\nkind: task\ntitle: Local\n"
            "publish_jira: true\njira_progress_comment_field: customfield_progress\n---\n\n"
            "# Summary\nLocal body\n",
            encoding="utf-8",
        )
        adapter = MemoryAdapter()
        apply_plan(self.repo, create_plan(self.repo), adapter)
        record = next(iter(adapter.records.values()))
        record["payload"]["title"] = "Remote title"
        record["payload"]["progress_comment"] = "Remote progress"

        check(self.repo, adapter)
        result = apply_plan(self.repo, create_plan(self.repo), adapter)

        self.assertEqual(result[0]["action"], "import")
        updated = path.read_text(encoding="utf-8")
        self.assertIn("title: 'Remote title'", updated)
        self.assertIn("# Progress Comment\n\nRemote progress", updated)

    def test_apply_creates_unpublished_confluence_parent_before_child(self):
        parent = self.repo / "documents" / "parent.md"
        child = parent.with_suffix("") / "child.md"
        child.parent.mkdir()
        parent.write_text(
            "---\ngtd_id: parent\nkind: document\ntitle: Parent\npublish_confluence: true\nconfluence_space_id: space-1\nconfluence_space_key: DOC\n---\n\n# Parent\n",
            encoding="utf-8",
        )
        child.write_text(
            "---\ngtd_id: child\nkind: document\ntitle: Child\npublish_confluence: true\nconfluence_space_id: space-1\nconfluence_space_key: DOC\nconfluence_parent_path: documents/parent.md\n---\n\n# Child\n",
            encoding="utf-8",
        )
        plan = create_plan(self.repo)
        adapter = MemoryAdapter()

        apply_plan(self.repo, plan, adapter)

        child_record = next(
            record
            for record in adapter.records.values()
            if record["payload"]["title"] == "Child"
        )
        parent_record = next(
            record
            for record in adapter.records.values()
            if record["payload"]["title"] == "Parent"
        )
        self.assertEqual(child_record["payload"]["parent_id"], parent_record["url"].rsplit("/", 1)[-1])
        self.assertIn(
            "confluence_parent_id: 'MEM-1'",
            child.read_text(encoding="utf-8"),
        )

    def test_apply_rejects_unresolved_confluence_parent_before_child_write(self):
        child = self.repo / "documents" / "child.md"
        child.write_text(
            "---\ngtd_id: child\nkind: document\ntitle: Child\npublish_confluence: true\nconfluence_space_id: space-1\nconfluence_space_key: DOC\nconfluence_parent_path: documents/missing.md\n---\n\n# Child\n",
            encoding="utf-8",
        )
        plan = create_plan(self.repo)
        adapter = MemoryAdapter()

        with self.assertRaisesRegex(SyncError, "parent page is unresolved"):
            apply_plan(self.repo, plan, adapter)
        self.assertEqual(adapter.records, {})

    def test_explicit_parent_path_never_falls_back_to_default_parent(self):
        child = self.repo / "documents" / "child.md"
        child.write_text(
            "---\ngtd_id: child\nkind: document\ntitle: Child\npublish_confluence: true\nconfluence_space_id: space-1\nconfluence_space_key: DOC\nconfluence_parent_path: documents/missing.md\n---\n\n# Child\n",
            encoding="utf-8",
        )
        with patch.dict(
            os.environ, {"CONFLUENCE_PARENT_ID": "default-parent"}, clear=False
        ):
            plan = create_plan(self.repo)
        with self.assertRaisesRegex(SyncError, "parent page is unresolved"):
            apply_plan(self.repo, plan, MemoryAdapter())

    def test_explicit_parent_paths_are_applied_in_dependency_order(self):
        parent = self.repo / "documents" / "parent.md"
        child = self.repo / "documents" / "child.md"
        parent.write_text(
            "---\nkind: document\ntitle: Parent\npublish_confluence: true\n---\n\n# Parent\n",
            encoding="utf-8",
        )
        child.write_text(
            "---\nkind: document\ntitle: Child\npublish_confluence: true\nconfluence_parent_path: documents/parent.md\n---\n\n# Child\n",
            encoding="utf-8",
        )
        plan = create_plan(self.repo)
        self.assertEqual(
            [action["path"] for action in plan["actions"]],
            ["documents/parent.md", "documents/child.md"],
        )

    def test_cyclic_confluence_parent_paths_are_rejected(self):
        for name, parent_path in (("a", "documents/b.md"), ("b", "documents/a.md")):
            (self.repo / "documents" / (name + ".md")).write_text(
                "---\nkind: document\ntitle: {}\npublish_confluence: true\nconfluence_parent_path: {}\n---\n\n# {}\n".format(
                    name, parent_path, name
                ),
                encoding="utf-8",
            )
        with self.assertRaisesRegex(SyncError, "cyclic Confluence"):
            create_plan(self.repo)

    def test_plan_infers_document_parent_from_recursive_path(self):
        parent = self.repo / "documents" / "parent.md"
        child = parent.with_suffix("") / "child.md"
        child.parent.mkdir()
        parent.write_text(
            "---\nkind: document\ntitle: Parent\npublish_confluence: true\n---\n\n# Parent\n",
            encoding="utf-8",
        )
        child.write_text(
            "---\nkind: document\ntitle: Child\npublish_confluence: true\n---\n\n# Child\n",
            encoding="utf-8",
        )

        plan = create_plan(self.repo)

        child_action = next(
            action for action in plan["actions"] if action["path"] == "documents/parent/child.md"
        )
        self.assertEqual(child_action["parent_path"], "documents/parent.md")

    def test_stale_plan_is_rejected(self):
        path = self.repo / "documents" / "guide.md"
        path.write_text(
            """---
gtd_id: 'doc-1'
kind: 'document'
title: 'Guide'
publish_confluence: 'true'
---

# Guide
""",
            encoding="utf-8",
        )
        plan = create_plan(self.repo)
        path.write_text(
            path.read_text(encoding="utf-8") + "\nChanged.\n", encoding="utf-8"
        )
        with self.assertRaises(SyncError):
            apply_plan(self.repo, plan, MemoryAdapter())

    def test_markdown_renderer_keeps_authoring_model(self):
        rendered = markdown_to_storage(
            "# Title\n\n:::confluence-macro name=info\nBody\n:::\n"
        )
        self.assertIn("<h1>Title</h1>", rendered)
        self.assertIn("ac:structured-macro", rendered)
        document = self.repo / "documents" / "guide.md"
        document.write_text(
            "---\nkind: 'document'\ntitle: 'Guide'\n---\n\n# Guide\n", encoding="utf-8"
        )
        self.assertEqual(parse_document(str(document)).metadata["kind"], "document")

    def test_public_payloads_support_blocks_without_private_content(self):
        document = self.repo / "documents" / "guide.md"
        document.write_text(
            """---
gtd_id: 'doc-1'
kind: 'document'
title: 'Guide'
publish_confluence: true
confluence_space_id: space-1
confluence_space_key: DOC
---

# Guide

| Name | Value |
| --- | --- |
| A | 1 |

[Private reference](documents/secret.md)
[Public reference](https://example.com/public)

# Implementation Note

private-token
""",
            encoding="utf-8",
        )
        task = self.repo / "gtd_tasks" / "task.md"
        task.write_text(
            """---
gtd_id: 'task-1'
kind: 'task'
title: 'Task'
publish_jira: true
jira_project: DEMO
---

# Summary

- one
- two

# Description

[Public task reference](https://example.com/public)

# Implementation Note

private-task-note
""",
            encoding="utf-8",
        )
        plan = create_plan(self.repo)
        by_kind = {action["kind"]: action["payload"] for action in plan["actions"]}
        confluence_body = by_kind["confluence"]["storage_body"]
        jira_body = by_kind["jira"]["description"]
        serialized_jira = jira_body
        for value in (confluence_body, serialized_jira):
            self.assertNotIn("private-token", value)
            self.assertNotIn("private-task-note", value)
            self.assertNotIn("documents/secret.md", value)
        self.assertIn("https://example.com/public", confluence_body)
        self.assertIn("https://example.com/public", serialized_jira)
        self.assertIn("<th>Name</th>", confluence_body)
        self.assertNotIn("h1. Summary", jira_body)
        self.assertNotIn("* one", jira_body)
        self.assertIn("[Public task reference|https://example.com/public]", jira_body)

    def test_apply_marks_two_sided_change_for_vim_resolution(self):
        path = self.repo / "documents" / "guide.md"
        path.write_text(
            """---
gtd_id: 'doc-1'
kind: 'document'
title: 'Guide'
publish_confluence: 'true'
---

# Guide

Base content.
""",
            encoding="utf-8",
        )
        plan = create_plan(self.repo)
        adapter = MemoryAdapter()
        apply_plan(self.repo, plan, adapter)
        path.write_text(
            path.read_text(encoding="utf-8").replace("Base content.", "Local content."),
            encoding="utf-8",
        )
        record = next(iter(adapter.records.values()))
        record["payload"]["storage_body"] = "<h1>Guide</h1><p>Remote content.</p>"
        check(self.repo, adapter)
        plan = create_plan(self.repo)
        with self.assertRaisesRegex(SyncError, "conflict"):
            apply_plan(self.repo, plan, adapter)
        merged = path.read_text(encoding="utf-8")
        self.assertIn("<<<<<<< local", merged)
        self.assertIn(">>>>>>> external", merged)

    def test_relative_reference_uses_published_external_url(self):
        target = self.repo / "documents" / "target.md"
        target.write_text(
            "---\nkind: 'document'\nconfluence_url: 'https://example.invalid/page'\n---\n\n# Target\n",
            encoding="utf-8",
        )
        source = self.repo / "gtd_tasks" / "task.md"
        source.write_text(
            "---\nkind: 'task'\n---\n\n[Target](../documents/target.md)\n",
            encoding="utf-8",
        )
        rendered = externalize_references(
            self.repo, "[Target](../documents/target.md)", source
        )
        self.assertEqual(rendered, "[Target](https://example.invalid/page)")

    def test_apply_adds_clickable_external_reference_to_task_markdown(self):
        path = self.repo / "gtd_tasks" / "task.md"
        path.write_text(
            """---
gtd_id: 'task-1'
kind: 'task'
title: 'Task'
publish_jira: 'true'
jira_project: 'DEMO'
jira_issue_type: 'Task'
---

# Summary

Task summary.

# References

- Internal design note

# Implementation Note

Private note.
""",
            encoding="utf-8",
        )

        apply_plan(self.repo, create_plan(self.repo), MemoryAdapter())

        updated = path.read_text(encoding="utf-8")
        self.assertIn(
            "- Jira: [MEM-1](https://memory.invalid/jira/MEM-1)", updated
        )
        self.assertIn("- Internal design note", updated)
        self.assertIn("# Implementation Note\n\nPrivate note.", updated)

    def test_structured_references_publish_external_links_without_local_paths(self):
        target = self.repo / "documents" / "target.md"
        target.write_text(
            "---\nkind: document\nconfluence_url: 'https://example.invalid/target'\n---\n\n# Target\n",
            encoding="utf-8",
        )
        source = self.repo / "gtd_tasks" / "task.md"
        source.write_text(
            "---\nkind: task\npublish_jira: true\nreferences:\n"
            "  - documents/target.md\n---\n\n# Summary\nTask\n",
            encoding="utf-8",
        )

        payload = create_plan(self.repo)["actions"][0]["payload"]

        self.assertIn("https://example.invalid/target", json.dumps(payload))
        self.assertNotIn("documents/target.md", json.dumps(payload))

    def test_jira_payload_keeps_progress_comment_as_configured_text_field(self):
        path = self.repo / "gtd_tasks" / "task.md"
        path.write_text(
            """---
gtd_id: 'task-1'
kind: 'task'
title: 'Task'
publish_jira: 'true'
jira_project: 'JOB'
jira_progress_comment_field: 'customfield_12345'
---

# Summary

Summary.

# Progress Comment

2026-08-23: completed the first review.

# Objective

Objective.
""",
            encoding="utf-8",
        )
        plan = create_plan(self.repo)
        payload = plan["actions"][0]["payload"]
        self.assertEqual(payload["progress_comment_field"], "customfield_12345")
        self.assertIn("2026-08-23", payload["progress_comment"])

    def test_jira_description_uses_only_description_section(self):
        path = self.repo / "gtd_tasks" / "task.md"
        path.write_text(
            """---
gtd_id: 'task-1'
kind: 'task'
title: 'Task title'
publish_jira: 'true'
jira_project: 'JOB'
---

# Summary

Jira summary comes from this Markdown section.

# Description

Only this description is sent to Jira.

# Progress Comment

2026-08-23: progress must use its own field.

# Objective

Objective must not be sent as the Jira description.
""",
            encoding="utf-8",
        )

        payload = create_plan(self.repo)["actions"][0]["payload"]

        self.assertIn("Only this description is sent to Jira.", payload["description"])
        self.assertEqual(payload["title"], "Jira summary comes from this Markdown section.")
        self.assertNotIn("Jira summary comes from", payload["description"])
        self.assertNotIn("progress must use its own field", payload["description"])
        self.assertNotIn("Objective must not be sent", payload["description"])

    def test_jira_check_compares_only_description_section(self):
        path = self.repo / "gtd_tasks" / "task.md"
        path.write_text(
            """---
gtd_id: 'task-1'
kind: 'task'
title: 'Task title'
publish_jira: 'true'
jira_project: 'JOB'
---

# Summary

Jira summary.

# Description

Jira description.

# Objective

Local-only objective.
""",
            encoding="utf-8",
        )
        adapter = MemoryAdapter()

        apply_plan(self.repo, create_plan(self.repo), adapter)

        observation = check(self.repo, adapter)

        self.assertEqual(observation["items"][0]["state"], "clean")

    def test_sync_payload_uses_environment_defaults_for_missing_front_matter(self):
        jira = self.repo / "gtd_tasks" / "task.md"
        jira.write_text(
            "---\ngtd_id: task-1\nkind: task\ntitle: Task\npublish_jira: true\n---\n\n# Summary\n",
            encoding="utf-8",
        )
        document = self.repo / "documents" / "guide.md"
        document.write_text(
            "---\ngtd_id: doc-1\nkind: document\ntitle: Guide\npublish_confluence: true\n---\n\n# Guide\n",
            encoding="utf-8",
        )
        defaults = {
            "JIRA_PROJECT": "LCL",
            "JIRA_ISSUE_TYPE": "Story",
            "JIRA_PROGRESS_COMMENT_FIELD": "customfield_progress",
            "CONFLUENCE_SPACE_ID": "space-local",
            "CONFLUENCE_SPACE_KEY": "DOCS",
            "CONFLUENCE_PARENT_ID": "parent-local",
        }
        with patch.dict(os.environ, defaults, clear=False):
            plan = create_plan(self.repo)
        by_kind = {action["kind"]: action["payload"] for action in plan["actions"]}
        self.assertEqual(by_kind["jira"]["project"], "LCL")
        self.assertEqual(by_kind["jira"]["issue_type"], "Story")
        self.assertEqual(
            by_kind["jira"]["progress_comment_field"], "customfield_progress"
        )
        self.assertEqual(by_kind["confluence"]["space_id"], "space-local")
        self.assertEqual(by_kind["confluence"]["space_key"], "DOCS")
        self.assertEqual(by_kind["confluence"]["parent_id"], "parent-local")

    def test_sync_payload_assigns_new_jira_issues_to_current_user_by_default(self):
        jira = self.repo / "gtd_tasks" / "task.md"
        jira.write_text(
            "---\ngtd_id: task-1\nkind: task\ntitle: Task\npublish_jira: true\n---\n\n# Summary\n",
            encoding="utf-8",
        )
        with patch.dict(os.environ, {"JIRA_ASSIGN_TO_SELF": "true"}, clear=False):
            payload = create_plan(self.repo)["actions"][0]["payload"]
        self.assertTrue(payload["assign_to_self"])

        with patch.dict(os.environ, {"JIRA_ASSIGN_TO_SELF": "false"}, clear=False):
            payload = create_plan(self.repo)["actions"][0]["payload"]
        self.assertFalse(payload["assign_to_self"])

    def test_sync_status_reports_local_state(self):
        plans = self.repo / ".jobutils" / "sync" / "plans"
        bases = self.repo / ".jobutils" / "sync" / "bases"
        plans.mkdir(parents=True)
        bases.mkdir(parents=True)
        action = {
            "action_id": "action-1",
            "action": "create",
            "kind": "confluence",
            "path": "documents/guide.md",
            "external_id": None,
            "payload": {
                "title": "Guide",
                "storage_body": "<h1>Guide</h1>",
                "space_id": "space-1",
                "space_key": "DOCS",
                "version": 0,
            },
        }
        (plans / "plan-1.json").write_text(
            json.dumps(
                {
                    "plan_id": "plan-1",
                    "created_at": "2026-08-25T10:00:00Z",
                    "source_hash": "0" * 64,
                    "actions": [action, dict(action, action_id="action-2")],
                }
            ),
            encoding="utf-8",
        )
        (plans / "plan-2.json").write_text(
            json.dumps(
                {
                    "plan_id": "plan-2",
                    "created_at": "2026-08-24T10:00:00Z",
                    "source_hash": "1" * 64,
                    "actions": [
                        action,
                        dict(action, action_id="action-2"),
                        dict(action, action_id="action-3"),
                    ],
                }
            ),
            encoding="utf-8",
        )
        (plans / "plan-3.json").write_text(
            '{"source_hash": "invalid", "actions": "not-a-list"}\n',
            encoding="utf-8",
        )
        os.utime(plans / "plan-1.json", (100, 100))
        os.utime(plans / "plan-2.json", (200, 200))
        os.utime(plans / "plan-3.json", (300, 300))
        (bases / "base-1.md").write_text("# Base\n", encoding="utf-8")
        (self.repo / "documents" / "guide.md").write_text(
            "---\nkind: document\n---\n\n<<<<<<< local\nLocal\n=======\nRemote\n>>>>>>> external\n",
            encoding="utf-8",
        )

        expected = {
            "base_count": 1,
            "conflict_count": 1,
            "error_count": 0,
            "latest_plan": ".jobutils/sync/plans/plan-2.json",
            "last_sync_at": None,
            "pending_actions": 3,
            "plan_count": 2,
            "read_error_count": 0,
        }
        self.assertEqual(sync_status(self.repo), expected)

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["sync", "status", "--repo", str(self.repo)]), 0)
        self.assertEqual(json.loads(output.getvalue()), expected)

    def test_apply_plan_rejects_paths_outside_managed_roots(self):
        document = self.repo / "documents" / "guide.md"
        document.write_text(
            "---\nkind: document\ntitle: Guide\npublish_confluence: true\n---\n\n# Guide\n",
            encoding="utf-8",
        )
        plan = create_plan(self.repo)
        plan["actions"][0]["path"] = "../outside.md"

        with self.assertRaisesRegex(SyncError, "invalid structure"):
            apply_plan(self.repo, plan, MemoryAdapter())

    def test_rebind_updates_jira_identity_without_external_write(self):
        path = self.repo / "gtd_tasks" / "task.md"
        path.write_text(
            "---\ngtd_id: task-1\nkind: task\npublish_jira: true\njira_key: null\njira_url: null\n---\n\n# Summary\n",
            encoding="utf-8",
        )

        result = rebind(
            self.repo,
            "gtd_tasks/task.md",
            "jira",
            "DEMO-42",
            "https://example.invalid/browse/DEMO-42",
        )

        self.assertEqual(result, path.resolve())
        text = path.read_text(encoding="utf-8")
        self.assertIn("jira_key: 'DEMO-42'", text)
        self.assertIn("jira_url: 'https://example.invalid/browse/DEMO-42'", text)

    def test_rebind_updates_confluence_page_and_parent_identity(self):
        path = self.repo / "documents" / "guide.md"
        path.write_text(
            "---\ngtd_id: doc-1\nkind: document\npublish_confluence: true\nconfluence_page_id: null\nconfluence_url: null\nconfluence_parent_id: null\n---\n\n# Guide\n",
            encoding="utf-8",
        )

        rebind(
            self.repo,
            "documents/guide.md",
            "confluence",
            "PAGE-42",
            "https://example.invalid/wiki/pages/PAGE-42",
            "PARENT-9",
        )

        text = path.read_text(encoding="utf-8")
        self.assertIn("confluence_page_id: 'PAGE-42'", text)
        self.assertIn(
            "confluence_url: 'https://example.invalid/wiki/pages/PAGE-42'", text
        )
        self.assertIn("confluence_parent_id: 'PARENT-9'", text)

    def test_rebind_confluence_parent_updates_children_atomically(self):
        parent = self.repo / "documents" / "parent.md"
        child = self.repo / "documents" / "child.md"
        parent.write_text(
            "---\nkind: document\nconfluence_page_id: 'OLD-PAGE'\n---\n\n# Parent\n",
            encoding="utf-8",
        )
        child.write_text(
            "---\nkind: document\nconfluence_parent_id: 'OLD-PAGE'\n---\n\n# Child\n",
            encoding="utf-8",
        )

        rebind(
            self.repo,
            "documents/parent.md",
            "confluence",
            "NEW-PAGE",
            "https://example.invalid/wiki/pages/NEW-PAGE",
        )

        self.assertIn("confluence_page_id: 'NEW-PAGE'", parent.read_text())
        self.assertIn("confluence_parent_id: 'NEW-PAGE'", child.read_text())

    def test_rebind_rejects_invalid_target_before_mutation(self):
        path = self.repo / "documents" / "guide.md"
        original = "---\nkind: document\nconfluence_page_id: null\n---\n\n# Guide\n"
        path.write_text(original, encoding="utf-8")

        with self.assertRaisesRegex(SyncError, "unsafe external URL"):
            rebind(
                self.repo,
                "documents/guide.md",
                "confluence",
                "page-1",
                "javascript:alert(1)",
            )
        with self.assertRaisesRegex(SyncError, "unsafe external URL"):
            rebind(
                self.repo,
                "documents/guide.md",
                "confluence",
                "page-1",
                "https://user:secret@example.invalid/page-1",
            )

        self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_rebind_rejects_unmanaged_or_unsafe_paths(self):
        with self.assertRaisesRegex(SyncError, "unsafe Markdown path"):
            rebind(self.repo, "README.md", "jira", "DEMO-42")
        with self.assertRaisesRegex(SyncError, "unsafe Markdown path"):
            rebind(self.repo, "../outside.md", "jira", "DEMO-42")

    def test_rebind_clears_old_url_when_a_new_url_is_not_supplied(self):
        path = self.repo / "gtd_tasks" / "task.md"
        path.write_text(
            "---\nkind: task\njira_key: 'OLD-1'\njira_url: 'https://example.invalid/old'\n---\n\n# Summary\n",
            encoding="utf-8",
        )

        rebind(self.repo, "gtd_tasks/task.md", "jira", "DEMO-42")

        text = path.read_text(encoding="utf-8")
        self.assertIn("jira_key: 'DEMO-42'", text)
        self.assertIn("jira_url: ''", text)

    def test_rebind_rejects_malformed_front_matter_before_mutation(self):
        path = self.repo / "documents" / "guide.md"
        original = "---\nthis is not yaml\n---\n\n# Guide\n"
        path.write_text(original, encoding="utf-8")

        with self.assertRaisesRegex(SyncError, "invalid YAML"):
            rebind(self.repo, "documents/guide.md", "confluence", "PAGE-42")

        self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_rebind_cli_updates_the_requested_file(self):
        path = self.repo / "documents" / "guide.md"
        path.write_text(
            "---\nkind: document\nconfluence_page_id: null\n---\n\n# Guide\n",
            encoding="utf-8",
        )

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(
                main(
                    [
                        "sync",
                        "rebind",
                        "--repo",
                        str(self.repo),
                        "--path",
                        "documents/guide.md",
                        "--kind",
                        "confluence",
                        "--external-id",
                        "PAGE-42",
                    ]
                ),
                0,
            )
        self.assertIn("documents/guide.md", output.getvalue())
        self.assertIn("confluence_page_id: 'PAGE-42'", path.read_text())

    def test_jira_parent_is_resolved_when_parent_is_created_in_same_plan(self):
        parent = self.repo / "gtd_tasks" / "parent.md"
        child = parent.with_suffix("") / "child.md"
        child.parent.mkdir()
        parent.write_text(
            "---\ngtd_id: parent\nkind: task\ntitle: Parent\npublish_jira: true\njira_project: DEMO\n---\n\n# Summary\nParent\n",
            encoding="utf-8",
        )
        child.write_text(
            "---\ngtd_id: child\nkind: task\ntitle: Child\npublish_jira: true\njira_project: DEMO\njira_issue_type: Sub-task\njira_parent_path: gtd_tasks/parent.md\njira_parent_key: null\n---\n\n# Summary\nChild\n",
            encoding="utf-8",
        )

        plan = create_plan(self.repo)
        self.assertEqual(
            [action["path"] for action in plan["actions"]],
            ["gtd_tasks/parent.md", "gtd_tasks/parent/child.md"],
        )
        adapter = MemoryAdapter()
        apply_plan(self.repo, plan, adapter)

        child_record = next(
            record
            for record in adapter.records.values()
            if record["payload"]["title"] == "Child"
        )
        parent_record = next(
            record
            for record in adapter.records.values()
            if record["payload"]["title"] == "Parent"
        )
        self.assertEqual(
            child_record["payload"]["parent_key"],
            parent_record["url"].rsplit("/", 1)[-1],
        )

    def test_jira_parent_path_without_parent_identity_fails_before_child_write(self):
        child = self.repo / "gtd_tasks" / "child.md"
        child.write_text(
            "---\ngtd_id: child\nkind: task\ntitle: Child\npublish_jira: true\njira_project: DEMO\njira_parent_path: gtd_tasks/missing.md\njira_parent_key: null\n---\n\n# Summary\nChild\n",
            encoding="utf-8",
        )
        adapter = MemoryAdapter()

        with self.assertRaisesRegex(SyncError, "Jira parent issue is unresolved"):
            apply_plan(self.repo, create_plan(self.repo), adapter)
        self.assertEqual(adapter.records, {})

    def test_cyclic_jira_parent_paths_are_rejected(self):
        for name, parent_path in (
            ("a", "gtd_tasks/b.md"),
            ("b", "gtd_tasks/a.md"),
        ):
            (self.repo / "gtd_tasks" / (name + ".md")).write_text(
                "---\nkind: task\ntitle: {}\npublish_jira: true\njira_parent_path: {}\n---\n\n# Summary\n{}\n".format(
                    name, parent_path, name
                ),
                encoding="utf-8",
            )

        with self.assertRaisesRegex(SyncError, "cyclic Jira"):
            create_plan(self.repo)

    def test_parent_identity_changes_make_a_plan_stale(self):
        parent = self.repo / "gtd_tasks" / "parent.md"
        child = self.repo / "gtd_tasks" / "child.md"
        parent.write_text(
            "---\nkind: task\ntitle: Parent\njira_key: 'DEMO-1'\n---\n\n# Summary\nParent\n",
            encoding="utf-8",
        )
        child.write_text(
            "---\nkind: task\ntitle: Child\npublish_jira: true\njira_project: DEMO\njira_parent_path: gtd_tasks/parent.md\n---\n\n# Summary\nChild\n",
            encoding="utf-8",
        )

        plan = create_plan(self.repo)
        parent.write_text(
            parent.read_text(encoding="utf-8").replace("DEMO-1", "DEMO-2"),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(SyncError, "stale"):
            apply_plan(self.repo, plan, MemoryAdapter())

    def test_classify_drift_states(self):
        cases = (
            ("base\n", "base\n", "base\n", "clean"),
            ("base\n", "base\n", "remote\n", "external_changed"),
            ("base\n", "local\n", "base\n", "local_changed"),
            ("base\n", "local\n", "remote\n", "conflict"),
            ("base\n", "same\n", "same\n", "converged"),
            (None, "local\n", "remote\n", "unknown"),
        )
        for base, local, remote, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(classify_drift(base, local, remote), expected)

    def test_classify_drift_ignores_authoring_blank_line_spacing(self):
        self.assertEqual(
            classify_drift("# Guide\n\nBody\n", "# Guide\n\n\n\nBody\n", "# Guide\n\nBody\n"),
            "clean",
        )

    def test_sync_normalization_preserves_blank_lines_inside_code(self):
        body = "# Guide\n\n\n\n```cpp\nfirst\n\nsecond\n```\n"
        self.assertIn("first\n\nsecond", canonical_sync_body(body))

    def test_non_overlapping_two_sided_changes_are_merged_and_published(self):
        path = self.repo / "documents" / "guide.md"
        path.write_text(
            "---\ngtd_id: doc-1\nkind: document\ntitle: Guide\n"
            "publish_confluence: true\nconfluence_space_id: space-1\n"
            "confluence_space_key: DOC\n---\n\n# Guide\n\n\n\n"
            "Base first\n\n\n\nBase second\n",
            encoding="utf-8",
        )
        adapter = MemoryAdapter()
        apply_plan(self.repo, create_plan(self.repo), adapter)
        record = next(iter(adapter.records.values()))
        current = parse_document(str(path)).public_body
        record["payload"]["storage_body"] = markdown_to_storage(
            current.replace("\n\n\n\n", "\n\n")
        )
        remote_body = current.replace("Base second", "Remote second")
        record["payload"]["storage_body"] = markdown_to_storage(
            remote_body.replace("\n\n\n\n", "\n\n")
        )
        path.write_text(
            path.read_text(encoding="utf-8").replace("Base first", "Local first"),
            encoding="utf-8",
        )

        check(self.repo, adapter)
        plan = create_plan(self.repo)

        self.assertEqual(plan["actions"][0]["action"], "merge")
        apply_plan(self.repo, plan, adapter)

        updated = path.read_text(encoding="utf-8")
        self.assertIn("Local first", updated)
        self.assertIn("Remote second", updated)
        self.assertIn("# Guide\n\n\n\nLocal first", updated)
        fetched = adapter.fetch("confluence", next(iter(adapter.records)))
        self.assertIn("Local first", fetched["body_markdown"])
        self.assertIn("Remote second", fetched["body_markdown"])

    def test_check_reports_external_change_without_mutating_repository(self):
        path = self.repo / "documents" / "guide.md"
        path.write_text(
            "---\ngtd_id: doc-1\nkind: document\ntitle: Guide\npublish_confluence: true\nconfluence_space_id: space-1\nconfluence_space_key: DOC\n---\n\n# Guide\n\nBase\n",
            encoding="utf-8",
        )
        adapter = MemoryAdapter()
        apply_plan(self.repo, create_plan(self.repo), adapter)
        adapter.records["MEM-1"]["payload"]["storage_body"] = markdown_to_storage(
            "# Guide\n\nRemote\n"
        )
        before = path.read_bytes()
        base_files = {
            item: item.read_bytes()
            for item in (self.repo / ".jobutils" / "sync" / "bases").glob("*.md")
        }

        result = check(self.repo, adapter)

        self.assertEqual(result["error_count"], 0)
        self.assertEqual(result["items"][0]["state"], "external_changed")
        self.assertEqual(result["items"][0]["path"], "documents/guide.md")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(
            {
                item: item.read_bytes()
                for item in (self.repo / ".jobutils" / "sync" / "bases").glob("*.md")
            },
            base_files,
        )

    def test_plan_turns_external_only_change_into_import_action(self):
        path = self.repo / "documents" / "guide.md"
        path.write_text(
            "---\nkind: document\ntitle: Guide\npublish_confluence: true\n"
            "confluence_space_id: space-1\nconfluence_space_key: DOC\n---\n\n"
            "# Guide\n\nBase\n",
            encoding="utf-8",
        )
        adapter = MemoryAdapter()
        apply_plan(self.repo, create_plan(self.repo), adapter)
        adapter.records["MEM-1"]["payload"]["storage_body"] = markdown_to_storage(
            "# Guide\n\nRemote\n"
        )

        check_result = check(self.repo, adapter)
        plan = create_plan(self.repo)

        self.assertEqual(check_result["items"][0]["state"], "external_changed")
        self.assertEqual(plan["observation_id"], check_result["observation_id"])
        self.assertEqual(plan["actions"][0]["action"], "import")
        self.assertEqual(plan["actions"][0]["external_id"], "MEM-1")

    def test_plan_turns_two_sided_change_into_blocking_conflict(self):
        path = self.repo / "documents" / "guide.md"
        path.write_text(
            "---\nkind: document\ntitle: Guide\npublish_confluence: true\n"
            "confluence_space_id: space-1\nconfluence_space_key: DOC\n---\n\n"
            "# Guide\n\nBase\n",
            encoding="utf-8",
        )
        adapter = MemoryAdapter()
        apply_plan(self.repo, create_plan(self.repo), adapter)
        adapter.records["MEM-1"]["payload"]["storage_body"] = markdown_to_storage(
            "# Guide\n\nRemote\n"
        )
        check(self.repo, adapter)
        path.write_text(
            path.read_text(encoding="utf-8").replace("# Guide\n\nBase", "# Guide\n\nLocal"),
            encoding="utf-8",
        )

        plan = create_plan(self.repo)

        self.assertEqual(plan["actions"][0]["action"], "conflict")
        self.assertIn("local content changed", plan["actions"][0]["blocked_reason"])

    def test_apply_imports_external_change_from_the_checked_observation(self):
        path = self.repo / "documents" / "guide.md"
        path.write_text(
            "---\nkind: document\ntitle: Guide\npublish_confluence: true\n"
            "confluence_space_id: space-1\nconfluence_space_key: DOC\n---\n\n"
            "# Guide\n\nBase\n",
            encoding="utf-8",
        )
        adapter = MemoryAdapter()
        apply_plan(self.repo, create_plan(self.repo), adapter)
        adapter.records["MEM-1"]["payload"]["storage_body"] = markdown_to_storage(
            "# Guide\n\nRemote\n"
        )
        check(self.repo, adapter)
        plan = create_plan(self.repo)

        result = apply_plan(self.repo, plan, adapter)

        self.assertEqual(result[0]["action"], "import")
        self.assertIn("Remote", path.read_text(encoding="utf-8"))
        self.assertNotIn("Base\n", path.read_text(encoding="utf-8"))

    def test_plan_rejects_observation_with_remote_git_changes(self):
        path = self.repo / "documents" / "guide.md"
        path.write_text(
            "---\nkind: document\ntitle: Guide\npublish_confluence: true\n---\n\n# Guide\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(SyncError, "Git repository is remote_ahead"):
            create_plan(
                self.repo,
                {
                    "observation_id": "observation-1",
                    "git": {"state": "remote_ahead"},
                    "items": [],
                },
            )

    def test_apply_rejects_external_change_after_check_before_mutation(self):
        path = self.repo / "documents" / "guide.md"
        path.write_text(
            "---\nkind: document\ntitle: Guide\npublish_confluence: true\n"
            "confluence_space_id: space-1\nconfluence_space_key: DOC\n---\n\n"
            "# Guide\n\nBase\n",
            encoding="utf-8",
        )
        adapter = MemoryAdapter()
        apply_plan(self.repo, create_plan(self.repo), adapter)
        adapter.records["MEM-1"]["payload"]["storage_body"] = markdown_to_storage(
            "# Guide\n\nRemote one\n"
        )
        check(self.repo, adapter)
        plan = create_plan(self.repo)
        adapter.records["MEM-1"]["payload"]["storage_body"] = markdown_to_storage(
            "# Guide\n\nRemote two\n"
        )
        before = path.read_text(encoding="utf-8")

        with self.assertRaisesRegex(SyncError, "external record changed"):
            apply_plan(self.repo, plan, adapter)

        self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_apply_rejects_conflict_action_before_mutating(self):
        path = self.repo / "documents" / "guide.md"
        path.write_text(
            "---\nkind: document\ntitle: Guide\npublish_confluence: true\n"
            "confluence_space_id: space-1\nconfluence_space_key: DOC\n---\n\n"
            "# Guide\n\nBase\n",
            encoding="utf-8",
        )
        adapter = MemoryAdapter()
        apply_plan(self.repo, create_plan(self.repo), adapter)
        adapter.records["MEM-1"]["payload"]["storage_body"] = markdown_to_storage(
            "# Guide\n\nRemote\n"
        )
        check(self.repo, adapter)
        path.write_text(
            path.read_text(encoding="utf-8").replace("# Guide\n\nBase", "# Guide\n\nLocal"),
            encoding="utf-8",
        )
        plan = create_plan(self.repo)
        with self.assertRaisesRegex(SyncError, "conflict"):
            apply_plan(self.repo, plan, adapter)

        merged = path.read_text(encoding="utf-8")
        self.assertIn("<<<<<<< local", merged)
        self.assertIn(">>>>>>> external", merged)

    def test_resolved_conflict_is_published_as_update(self):
        path = self.repo / "documents" / "guide.md"
        path.write_text(
            "---\nkind: document\ntitle: Guide\npublish_confluence: true\n"
            "confluence_space_id: space-1\nconfluence_space_key: DOC\n---\n\n"
            "# Guide\n\nBase\n",
            encoding="utf-8",
        )
        adapter = MemoryAdapter()
        apply_plan(self.repo, create_plan(self.repo), adapter)
        adapter.records["MEM-1"]["payload"]["storage_body"] = markdown_to_storage(
            "# Guide\n\nRemote\n"
        )
        check(self.repo, adapter)
        path.write_text(
            path.read_text(encoding="utf-8").replace("# Guide\n\nBase", "# Guide\n\nLocal"),
            encoding="utf-8",
        )
        conflict_plan = create_plan(self.repo)
        with self.assertRaisesRegex(SyncError, "conflict"):
            apply_plan(self.repo, conflict_plan, adapter)

        conflict_text = path.read_text(encoding="utf-8")
        path.write_text(
            conflict_text[: conflict_text.index("<<<<<<< local")]
            + "# Guide\n\nResolved\n",
            encoding="utf-8",
        )

        check(self.repo, adapter)
        resolved_plan = create_plan(self.repo)
        self.assertEqual(resolved_plan["actions"][0]["action"], "update")
        apply_plan(self.repo, resolved_plan, adapter)

        self.assertIn(
            "Resolved",
            adapter.fetch("confluence", "MEM-1")["body_markdown"],
        )
        self.assertFalse(
            any(
                (self.repo / ".jobutils" / "sync" / "conflicts").glob("*.json")
            )
        )

    def test_check_isolates_fetch_errors_and_reports_missing_base(self):
        first = self.repo / "documents" / "first.md"
        second = self.repo / "documents" / "second.md"
        first.write_text(
            "---\nkind: document\ntitle: First\npublish_confluence: true\nconfluence_page_id: MEM-1\n---\n\n# First\n",
            encoding="utf-8",
        )
        second.write_text(
            "---\nkind: document\ntitle: Second\npublish_confluence: true\nconfluence_page_id: MEM-2\n---\n\n# Second\n",
            encoding="utf-8",
        )

        class FetchAdapter(MemoryAdapter):
            def fetch(self, kind, external_id, options=None):
                if external_id == "MEM-2":
                    raise RuntimeError("remote unavailable")
                return super().fetch(kind, external_id, options)

        adapter = FetchAdapter()
        adapter.records["MEM-1"] = {
            "kind": "confluence",
            "payload": {"title": "First", "storage_body": "<h1>First</h1>"},
            "url": "https://memory.invalid/confluence/MEM-1",
        }
        adapter.records["MEM-2"] = {
            "kind": "confluence",
            "payload": {"title": "Second", "storage_body": "<h1>Second</h1>"},
            "url": "https://memory.invalid/confluence/MEM-2",
        }

        result = check(self.repo, adapter)
        by_path = {item["path"]: item for item in result["items"]}
        self.assertEqual(result["error_count"], 1)
        self.assertEqual(by_path["documents/first.md"]["state"], "unknown")
        self.assertEqual(by_path["documents/second.md"]["state"], "error")
        self.assertIn("remote unavailable", by_path["documents/second.md"]["error"])

    def test_check_refreshes_git_and_saves_external_observation(self):
        repository = self.repo / "refresh-repo"
        repository.mkdir()
        (repository / "documents").mkdir()
        (repository / "gtd_tasks").mkdir()
        subprocess.run(["git", "init", "-q", str(repository)], check=True)
        subprocess.run(
            ["git", "config", "user.email", "local-test"],
            cwd=repository,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Job Utils Test"],
            cwd=repository,
            check=True,
        )
        remote = self.repo / "refresh-remote.git"
        subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
        subprocess.run(
            ["git", "remote", "add", "origin", str(remote)],
            cwd=repository,
            check=True,
        )
        document = repository / "documents" / "guide.md"
        document.write_text(
            "---\nkind: document\ntitle: Guide\npublish_confluence: true\n"
            "confluence_page_id: MEM-1\n---\n\n# Guide\n\nLocal\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "-A"], cwd=repository, check=True)
        subprocess.run(
            ["git", "commit", "-qm", "test: seed refresh repository"],
            cwd=repository,
            check=True,
        )
        subprocess.run(["git", "push", "-q", "origin", "HEAD"], cwd=repository, check=True)
        adapter = MemoryAdapter()
        adapter.records["MEM-1"] = {
            "kind": "confluence",
            "payload": {
                "title": "Guide",
                "storage_body": "<h1>Guide</h1><p>Remote</p>",
            },
            "url": "https://memory.invalid/confluence/MEM-1",
        }
        before = document.read_bytes()

        result = check(repository, adapter, refresh_git=True)

        self.assertEqual(result["git"]["remote"], "origin")
        self.assertTrue(result["git"]["performed"])
        self.assertEqual(result["items"][0]["state"], "unknown")
        observation = repository / ".jobutils" / "sync" / "observations" / "latest.json"
        self.assertTrue(observation.is_file())
        saved = json.loads(observation.read_text(encoding="utf-8"))
        self.assertEqual(saved["observation_id"], result["observation_id"])
        self.assertEqual(saved["items"][0]["remote"]["title"], "Guide")
        self.assertEqual(document.read_bytes(), before)

    def test_sync_check_cli_returns_json_and_error_status(self):
        path = self.repo / "documents" / "guide.md"
        path.write_text(
            "---\nkind: document\ntitle: Guide\npublish_confluence: true\nconfluence_page_id: MEM-1\n---\n\n# Guide\n",
            encoding="utf-8",
        )
        output = io.StringIO()
        errors = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            result = main(
                [
                    "sync",
                    "check",
                    "--repo",
                    str(self.repo),
                    "--adapter",
                    "memory",
                ]
            )

        self.assertEqual(result, 1)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["checked"], 1)
        self.assertEqual(payload["items"][0]["state"], "error")
        self.assertIn("SYNC: check failed", errors.getvalue())

    def test_sync_status_ignores_symlinked_plans(self):
        plans = self.repo / ".jobutils" / "sync" / "plans"
        plans.mkdir(parents=True)
        target = plans / "real.json"
        target.write_text(
            json.dumps(
                {
                    "plan_id": "real",
                    "created_at": "2026-08-25T10:00:00Z",
                    "source_hash": "0" * 64,
                    "actions": [],
                }
            ),
            encoding="utf-8",
        )
        try:
            (plans / "link.json").symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available")
        status = sync_status(self.repo)
        self.assertEqual(status["plan_count"], 1)
        self.assertEqual(status["latest_plan"], ".jobutils/sync/plans/real.json")


if __name__ == "__main__":
    unittest.main()
