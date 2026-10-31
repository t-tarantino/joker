"""Local GUI server: standard library only, listens on 127.0.0.1.

JSON API (the browser page in ./static talks to it):
    GET  /api/state          current table, odds, tracker and pending question
    POST /api/new            {"game": "scopone" | "briscola" | "blackjack", "setup": int}
    POST /api/choose         {"index": int}
    POST /api/undo
    POST /api/view           {} — only re-reads the state with another view

Every call may carry a VIEW — what the person selected, so only that is computed
(gui.md G6): {"focus": seat or pile key | null, "card": "suit/rank" | null}. GET
takes it as query parameters (?focus=p2&card=coins/7), POST as "view" in the body.
"""

from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .profiles import PROFILES

STATIC = Path(__file__).parent / "static"
CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                 ".js": "text/javascript; charset=utf-8", ".png": "image/png", ".svg": "image/svg+xml"}


class App:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.profile = None
        self.session = None

    def new(self, game: str, setup: int) -> None:
        profile = PROFILES[game]
        session = profile.new_session(setup)
        session.auto_advance()
        self.profile, self.session = profile, session

    def choose(self, index: int) -> None:
        pending = self.session.pending()
        _, who = self.profile.prompt(pending)
        choice = self.profile.choice_json(pending.choices[index])
        self.session.choose(index, self.profile.label(pending, who, choice))

    def undo(self) -> None:
        self.session.undo()

    def state(self, view: dict | None = None) -> dict:
        games = [p.public() for p in PROFILES.values()]
        if self.session is None:
            return {"session": False, "games": games}
        profile, session = self.profile, self.session
        engine = session.engine
        belief = session.belief()
        pending = session.pending()
        return {
            "session": True,
            "games": games,
            "game": profile.id,
            "title": profile.title,
            "layout": profile.layout,
            "deck": profile.deck(engine),
            "table": profile.table_view(engine, belief, view or {}, pending),
            "worlds": f"{belief.support:,}",
            "pending": _pending_json(profile, engine, belief, pending),
            "history": session.labels,
            "warnings": [f"Player {w.player + 1} broke the rule '{w.rule}' — it is no longer trusted for them"
                         for w in session.warnings],
        }


def _pending_json(profile, engine, belief, pending) -> dict | None:
    if pending is None:
        return None
    question, who = profile.prompt(pending)
    choices = []
    for i, c in enumerate(pending.choices):
        choice = {"index": i, **profile.choice_json(c)}
        choice["text"] = profile.describe(choice)
        choices.append(choice)
    values = profile.advice(engine, belief, pending, choices)
    if values:
        best = max(values, key=values.get)
        for choice in choices:
            if choice["index"] in values:
                choice["value"] = values[choice["index"]]
                choice["best"] = choice["index"] == best
    return {"question": question, "who": who, "choices": choices}


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):            # keep the terminal quiet
            pass

        def _send(self, status, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, data, status=HTTPStatus.OK) -> None:
            self._send(status, json.dumps(data).encode("utf-8"), "application/json")

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == "/api/state":
                query = parse_qs(url.query)
                view = {"focus": query.get("focus", [None])[0] or None,
                        "card": query.get("card", [None])[0] or None}
                with app.lock:
                    return self._json(app.state(view))
            name = "index.html" if url.path in ("/", "/index.html") else url.path.lstrip("/")
            target = (STATIC / name).resolve()
            if STATIC.resolve() not in target.parents or not target.is_file():
                return self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")
            self._send(HTTPStatus.OK, target.read_bytes(),
                       CONTENT_TYPES.get(target.suffix, "application/octet-stream"))

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                with app.lock:
                    if self.path == "/api/new":
                        app.new(body.get("game", "scopone"), int(body.get("setup", body.get("dealer", 0))))
                    elif self.path == "/api/choose":
                        app.choose(int(body["index"]))
                    elif self.path == "/api/undo":
                        app.undo()
                    elif self.path != "/api/view":
                        return self._json({"error": "unknown endpoint"}, HTTPStatus.NOT_FOUND)
                    return self._json(app.state(body.get("view") or {}))
            except Exception as exc:                  # surface errors to the page
                return self._json({"error": f"{type(exc).__name__}: {exc}"}, HTTPStatus.BAD_REQUEST)

    return Handler


def serve(port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(App()))
