"""GTD Markdown parsing and dispatch."""

from .dispatcher import DispatchError, DispatchResult, dispatch, create_task

__all__ = ["DispatchError", "DispatchResult", "dispatch", "create_task"]
