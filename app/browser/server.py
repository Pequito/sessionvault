"""Local HTTP server that the SessionVault browser extension talks to.

Binds exclusively to 127.0.0.1 so it is never reachable from the network.
Runs in a daemon thread managed by :class:`BrowserServer`.

API
---
GET  /ping
    Returns app name, version, and whether a KeePass database is open.

POST /get-logins        body: {"url": "https://example.com"}
    Returns all KeePass entries whose stored URL hostname matches the
    requested URL hostname.

POST /save-login        body: {"url": "…", "title": "…", "username": "…", "password": "…"}
    Adds a new KeePass entry to the active database under the group
    "Browser".  Returns {"success": true/false}.

POST /update-login      body: {"uuid": "…", "username": "…", "password": "…"}
    Updates an existing KeePass entry.  Returns {"success": true/false}.

All endpoints set permissive CORS headers so the browser extension (whose
origin is a chrome-extension:// or moz-extension:// URL) can reach them.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from app.constants import APP_NAME, APP_VERSION
from app.managers.keepass import keepass_manager
from app.managers.logger import get_logger

log = get_logger(__name__)

DEFAULT_PORT = 19456


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------

class _Handler(BaseHTTPRequestHandler):
    """HTTP request handler for the browser integration API."""

    # Silence the default per-request log to stderr; we use our own logger.
    def log_message(self, fmt: str, *args) -> None:
        log.debug("browser-server: " + fmt, *args)

    def log_error(self, fmt: str, *args) -> None:
        log.error("browser-server: " + fmt, *args)

    # ------------------------------------------------------------------
    # Verb dispatch
    # ------------------------------------------------------------------

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight."""
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        if self.path.split("?")[0] == "/ping":
            self._json({
                "appName":  APP_NAME,
                "version":  APP_VERSION,
                "dbOpen":   keepass_manager.is_open,
                "dbCount":  len(keepass_manager.open_paths),
            })
        else:
            self._json({"error": "not_found"}, 404)

    def do_POST(self) -> None:
        body = self._read_body()
        path = self.path.split("?")[0]

        if path == "/get-logins":
            self._handle_get_logins(body)
        elif path == "/save-login":
            self._handle_save_login(body)
        elif path == "/update-login":
            self._handle_update_login(body)
        else:
            self._json({"error": "not_found"}, 404)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _handle_get_logins(self, body: dict) -> None:
        url = body.get("url", "").strip()
        if not url:
            self._json({"error": "url_required"}, 400)
            return
        if not keepass_manager.is_open:
            self._json({"error": "no_database_open", "entries": []}, 200)
            return
        entries = keepass_manager.find_entries_for_url(url)
        log.debug(
            "get-logins: url=%s  matches=%d",
            urlparse(url).hostname, len(entries),
        )
        self._json({
            "entries": [
                {
                    "uuid":     str(e.uuid),
                    "title":    e.title    or "",
                    "username": e.username or "",
                    "password": e.password or "",
                    "url":      e.url      or "",
                }
                for e in entries
            ]
        })

    def _handle_save_login(self, body: dict) -> None:
        if not keepass_manager.is_open:
            self._json({"error": "no_database_open", "success": False}, 200)
            return
        url   = body.get("url",      "").strip()
        title = (body.get("title",   "").strip()
                 or urlparse(url).hostname
                 or "Saved Login")
        entry = keepass_manager.add_entry(
            group_name=body.get("group", "Browser"),
            title=title,
            username=body.get("username", ""),
            password=body.get("password", ""),
            url=url,
        )
        success = entry is not None
        log.info("save-login: title=%s  success=%s", title, success)
        self._json({"success": success})

    def _handle_update_login(self, body: dict) -> None:
        uid = body.get("uuid", "").strip()
        if not uid:
            self._json({"error": "uuid_required"}, 400)
            return
        ok = keepass_manager.update_entry(
            uid,
            username=body.get("username"),
            password=body.get("password"),
            url=body.get("url"),
            title=body.get("title"),
        )
        log.info("update-login: uuid=%s  success=%s", uid, ok)
        self._json({"success": ok})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except Exception:
            return {}

    def _json(self, data: dict, status: int = 200) -> None:
        payload = json.dumps(data).encode()
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type",   "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------

class BrowserServer:
    """Manages the lifecycle of the browser integration HTTP server.

    Call :meth:`start` once at application startup (when the feature is
    enabled) and :meth:`stop` on shutdown or when the user disables it.
    """

    def __init__(self) -> None:
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._port: int = DEFAULT_PORT

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def running(self) -> bool:
        return self._httpd is not None

    @property
    def port(self) -> int:
        return self._port

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, port: int = DEFAULT_PORT) -> None:
        """Start the server in a daemon thread.

        Raises :class:`OSError` if the port is already in use.
        """
        if self._httpd is not None:
            return
        self._port = port
        self._httpd = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="sessionvault-browser-server",
            daemon=True,
        )
        self._thread.start()
        log.info("Browser integration server listening on 127.0.0.1:%d", port)

    def stop(self) -> None:
        """Shut down the server gracefully."""
        if self._httpd is None:
            return
        self._httpd.shutdown()
        self._httpd = None
        self._thread = None
        log.info("Browser integration server stopped")

    def restart(self, port: int = DEFAULT_PORT) -> None:
        """Stop (if running) then start on *port*."""
        self.stop()
        self.start(port)


# Global singleton
browser_server = BrowserServer()
