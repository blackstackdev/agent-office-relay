"""Live Ollama + FalkorDB verification, isolated fictional data, no external calls."""
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agent import MODEL, coordinate, resume
from relay import Office, RelayError


def run():
    office = Office("relay_test_" + uuid4().hex)
    try:
        office.seed()
        first = coordinate(office, "What is blocking the Lantern release? Prepare a handoff for the review specialist.")
        assert [t["tool"] for t in first["tool_trace"]] == ["get_task_context", "propose_relay"]
        assert first["relay"]["status"] == "pending"
        assert "release-policy" in first["answer"], "Answer omitted original source citation."
        office.approve(first["relay"]["id"], human_confirmed=True)
        specialist = resume(office, first["relay"]["id"])
        assert specialist["fresh_session"] and not specialist["executed_work"]
        assert "release-policy" in specialist["answer"], "Specialist omitted scoped source."
        old = office.propose("launch", "reviewer")
        office.update_decision("cleared", "Policy amendment: the recovery drill evidence has been accepted. Review remains incomplete.")
        try:
            office.approve(old["id"], human_confirmed=True)
            raise AssertionError("Stale relay approval succeeded.")
        except RelayError:
            pass
        changed = coordinate(office, "The policy has changed. What is blocking the Lantern release now? Prepare a fresh review handoff.")
        assert changed["context"]["decisions"][0]["state"] == "cleared"
        assert changed["relay"]["revision"] == 2
        assert "release-policy-v2" in changed["answer"], "Amended answer omitted current source."
        evidence = {"date": "2026-10-15", "model": MODEL, "result": "PASS",
                    "runtime": "Local Ollama + real FalkorDB", "initial": first,
                    "specialist_fresh_session": specialist, "after_policy_amendment": changed,
                    "stale_approval_rejected": True, "human_approval_in_test": "scripted fixture only"}
        (ROOT / "evidence" / "live-model.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
        print(json.dumps({"result": "PASS", "model": MODEL, "initial_answer": first["answer"],
                          "specialist": specialist["answer"], "updated_answer": changed["answer"],
                          "coordinator_seconds": [first["seconds"], changed["seconds"]]}, indent=2))
    finally:
        office.graph.delete()


if __name__ == "__main__":
    run()
