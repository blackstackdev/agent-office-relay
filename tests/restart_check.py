"""Restart only this project's Compose graph service; verify synthetic relay memory."""
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from relay import Office


def run():
    name = "relay_test_" + uuid4().hex
    office = Office(name)
    office.seed()
    relay = office.propose("launch", "reviewer")
    office.approve(relay["id"], human_confirmed=True)
    packet = office.consume(relay["id"], "reviewer")
    for args in (["restart", "graph"], ["up", "-d", "--wait", "graph"]):
        result = subprocess.run(["docker", "compose", "-f", str(ROOT / "compose.yaml"), *args],
                                cwd=ROOT, capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise RuntimeError(result.stderr)
    # Fresh interpreter and client: no process-local state can supply the packet.
    read = subprocess.run([sys.executable, str(ROOT / "src" / "relay.py"), "--graph", name,
                           "consume", relay["id"], "reviewer"],
                          capture_output=True, text=True, timeout=15)
    if read.returncode:
        raise RuntimeError(read.stderr)
    if json.loads(read.stdout) != packet:
        raise AssertionError("Packet changed across server restart.")
    Office(name).graph.delete()
    evidence = {"date": "2026-10-15", "result": "PASS", "real_falkordb": True,
                "checks": ["Approved fictional relay saved to FalkorDB",
                           "Project database container restarted",
                           "Fresh Python process loaded identical approved packet",
                           "Isolated test graph removed"],
                "model_backed_agent_tested": False}
    (ROOT / "evidence" / "restart.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    run()
