"""Loopback-only local demonstrator. Human endpoints are separate from model tools."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import urlsplit

from agent import MODEL, coordinate, resume
from relay import Office, RelayError, VERSION

ROOT = Path(__file__).resolve().parents[1]
MODEL_LOCK = threading.Lock()
ALLOWED_HOSTS = {"127.0.0.1:4176", "localhost:4176"}
ALLOWED_ORIGINS = {"http://"+host for host in ALLOWED_HOSTS}


def state():
    office = Office()
    context = office.context("launch")
    relay_ids = office.query("""MATCH (:Project {id:'lantern'})-[:HAS_RELAY]->(r:Relay)
        RETURN r.id ORDER BY r.created_at DESC LIMIT 8""")
    runs = office.query("""MATCH (:Project {id:'lantern'})-[:HAS_RUN]->(r:AgentRun)
        RETURN r.id, r.kind, r.answer, r.revision, r.trace, r.model
        ORDER BY r.created_at DESC LIMIT 8""")
    return {"context": context, "relays": [office.get_relay(r[0]) for r in relay_ids],
            "runs": [{"id": r[0], "kind": r[1], "answer": r[2], "revision": r[3],
                      "trace": json.loads(r[4]), "model": r[5]} for r in runs],
            "model": MODEL, "version": VERSION}


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def json_response(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def local_request(self):
        return self.headers.get("Host") in ALLOWED_HOSTS

    def do_GET(self):
        if not self.local_request():
            return self.json_response(403, {"error": "Local host required."})
        if urlsplit(self.path).path == "/api/state":
            try:
                return self.json_response(200, state())
            except Exception:
                return self.json_response(503, {"error": "FalkorDB is unavailable. Start the local graph service and reload."})
        if self.path.startswith("/api/"):
            return self.json_response(404, {"error": "Unknown operation."})
        return super().do_GET()

    def do_POST(self):
        if (not self.local_request() or self.headers.get("Origin", "http://127.0.0.1:4176") not in ALLOWED_ORIGINS):
            return self.json_response(403, {"error": "Same-origin local requests required."})
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self.json_response(415, {"error": "JSON required."})
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 1 <= length <= 12000:
                return self.json_response(413, {"error": "Request size must be 1–12000 bytes."})
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError()
        except (ValueError, json.JSONDecodeError):
            return self.json_response(400, {"error": "Invalid JSON request."})
        route = urlsplit(self.path).path
        if route not in ("/api/ask", "/api/approve", "/api/resume", "/api/decision"):
            return self.json_response(404, {"error": "Unknown operation."})
        locked = False
        try:
            office = Office()
            if route in ("/api/ask", "/api/resume"):
                locked = MODEL_LOCK.acquire(blocking=False)
                if not locked:
                    return self.json_response(409, {"error": "A local model run is already working. Wait for it to finish."})
            if route == "/api/ask":
                if set(data) != {"question"}:
                    raise RelayError("Provide only a question.")
                result = coordinate(office, data["question"])
            elif route == "/api/approve":
                if set(data) != {"relay_id", "human_confirmed"} or data["human_confirmed"] is not True:
                    raise RelayError("Explicit human confirmation is required.")
                result = office.approve(data["relay_id"], human_confirmed=True)
            elif route == "/api/resume":
                if set(data) != {"relay_id", "recipient"} or data["recipient"] not in ("reviewer", "builder"):
                    raise RelayError("Provide the approved relay and its selected recipient.")
                result = resume(office, data["relay_id"], data["recipient"])
            else:
                if set(data) != {"state", "text"}:
                    raise RelayError("Provide decision state and source amendment text.")
                result = office.update_decision(data["state"], data["text"])
            return self.json_response(200, result)
        except RelayError as exc:
            return self.json_response(409, {"error": str(exc)})
        except Exception:
            return self.json_response(503, {"error": "The local operation failed. Check FalkorDB and Ollama, then retry."})
        finally:
            if locked:
                MODEL_LOCK.release()


if __name__ == "__main__":
    if not (ROOT / "web" / "dist" / "index.html").is_file():
        raise SystemExit("Build the frontend first: cd web; npm ci; npm run build")
    Office().seed()
    handler = partial(Handler, directory=str(ROOT / "web" / "dist"))
    server = ThreadingHTTPServer(("127.0.0.1", 4176), handler)
    print("Agent Office local prototype: http://127.0.0.1:4176", flush=True)
    server.serve_forever()
