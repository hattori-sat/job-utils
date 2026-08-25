"""Local HTTP interface over safe job-utils operations."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from .gtd import DispatchError, dispatch
from .metrics.reports import build_report
from .sync.engine import SyncError, create_plan, save_plan


def _json_bytes(value: Dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def create_server(repo_root: Path, host: str = "127.0.0.1", port: int = 8765):
    """Create a local HTTP server for GTD dispatch, plans, and reports."""

    repo_root = Path(repo_root).resolve()

    class Handler(BaseHTTPRequestHandler):
        server_version = "job-utils/0.1"

        def log_message(self, format, *args):
            return

        def _send(self, status: int, payload: Dict[str, Any]) -> None:
            body = _json_bytes(payload)
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self) -> Dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as error:
                raise ValueError("invalid Content-Length") from error
            if length > 1024 * 1024:
                raise ValueError("request body is too large")
            if not length:
                return {}
            value = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("request body must be a JSON object")
            return value

        def do_GET(self):
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if parsed.path == "/health":
                self._send(200, {"status": "ok"})
                return
            if parsed.path == "/metrics":
                start = query.get("from", [None])[0]
                end = query.get("to", [None])[0]
                if not start or not end:
                    self._send(400, {"error": "metrics requires from and to"})
                    return
                try:
                    self._send(200, build_report(repo_root, start, end))
                except (ValueError, OSError) as error:
                    self._send(400, {"error": str(error)})
                return
            self._send(404, {"error": "not found"})

        def do_POST(self):
            try:
                body = self._read_json()
                if self.path == "/gtd/dispatch":
                    result = dispatch(
                        repo_root,
                        repo_root / "gtd.md",
                        body.get("machine_id"),
                    )
                    self._send(
                        200,
                        {
                            "gtd_path": str(result.gtd_path),
                            "moved": result.moved,
                            "created": [str(path) for path in result.created],
                            "event_count": result.event_count,
                        },
                    )
                    return
                if self.path == "/sync/plan":
                    plan = create_plan(repo_root)
                    path = save_plan(repo_root, plan)
                    self._send(
                        200,
                        {
                            "plan_id": plan["plan_id"],
                            "actions": len(plan["actions"]),
                            "path": str(path),
                        },
                    )
                    return
            except (DispatchError, SyncError, OSError, ValueError, KeyError) as error:
                self._send(400, {"error": str(error)})
                return
            self._send(404, {"error": "not found"})

    return ThreadingHTTPServer((host, port), Handler)


def serve(repo_root: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run the local HTTP interface until interrupted."""

    server = create_server(repo_root, host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
