"""Non-secret synchronization defaults supplied by the local environment."""

import os
from typing import Dict


def load_sync_defaults() -> Dict[str, str]:
    """Read publish defaults without ever reading or returning credentials."""

    return {
        "jira_project": os.environ.get("JIRA_PROJECT", ""),
        "jira_issue_type": os.environ.get("JIRA_ISSUE_TYPE", "Task") or "Task",
        "jira_progress_comment_field": os.environ.get(
            "JIRA_PROGRESS_COMMENT_FIELD", ""
        ),
        "confluence_space_id": os.environ.get("CONFLUENCE_SPACE_ID", ""),
        "confluence_space_key": os.environ.get("CONFLUENCE_SPACE_KEY", ""),
        "confluence_parent_id": os.environ.get("CONFLUENCE_PARENT_ID", ""),
    }
