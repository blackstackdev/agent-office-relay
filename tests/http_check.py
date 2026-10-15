"""Local HTTP boundary smoke check. Start src/server.py first."""
import json
from pathlib import Path
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:4176"


def request(path, data=None, headers=None):
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(BASE+path,
        data=json.dumps(data).encode() if data is not None else None, headers=request_headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


checks = []
status, state = request("/api/state")
assert status == 200 and state["context"]["project"] == "lantern"
checks.append("Real graph state available via same-origin local endpoint")
assert request("/api/approve", {"relay_id": "missing", "human_confirmed": True},
               {"Origin": "https://unrelated.example"})[0] == 403
checks.append("Cross-origin approval request rejected")
assert request("/api/approve", {"relay_id": "missing", "human_confirmed": False})[0] == 409
checks.append("Approval without explicit confirmation rejected")
assert request("/api/execute", {})[0] == 404
checks.append("No arbitrary execution endpoint")
assert request("/api/ask", {"question": "x" * 13000})[0] == 413
checks.append("Oversized request rejected before inference")
evidence = {"date": "2026-10-15", "result": "PASS", "checks": checks,
            "scope": "Local prototype boundary checks; not a security audit"}
(ROOT / "evidence" / "http-checks.json").write_text(json.dumps(evidence, indent=2)+"\n", encoding="utf-8")
print(json.dumps(evidence, indent=2))
