"""Canonical GTD prefixes and the parsed item value object."""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


PREFIXES: Tuple[str, ...] = (
    "inbox",
    "next",
    "today",
    "focus",
    "wait",
    "cal",
    "someday",
    "project",
    "done",
)

SECTIONS: Dict[str, str] = {
    "inbox": "Inbox",
    "next": "Next Actions",
    "today": "Today",
    "focus": "Focus",
    "wait": "Waiting",
    "cal": "Calendar",
    "someday": "Someday",
    "project": "Projects",
    "done": "Done",
}

STATUSES: Dict[str, str] = {
    "inbox": "inbox",
    "next": "open",
    "today": "in_progress",
    "focus": "active",
    "wait": "waiting",
    "cal": "scheduled",
    "someday": "deferred",
    "project": "active",
    "done": "done",
}

SECTION_TO_PREFIX: Dict[str, str] = {
    section: prefix for prefix, section in SECTIONS.items()
}


@dataclass(frozen=True)
class TaskItem:
    """A recognized list item in the GTD index."""

    line_index: int
    title: str
    prefix: str
    section: str
    link: Optional[str]
    explicitly_prefixed: bool

    @property
    def source_prefix(self) -> str:
        return SECTION_TO_PREFIX.get(self.section, "inbox")

    @property
    def rendered_body(self) -> str:
        if self.link:
            return "{} <{}>".format(self.title, self.link)
        return self.title

    @property
    def rendered_line(self) -> str:
        return "- {}: {}".format(self.prefix, self.rendered_body)
