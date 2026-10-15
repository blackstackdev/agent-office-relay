"""Integration checks against real FalkorDB, each in an isolated fictional graph."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from relay import Office, RelayError


class GraphChecks(unittest.TestCase):
    def setUp(self):
        self.name = "relay_test_" + uuid4().hex
        self.office = Office(self.name)
        self.office.seed()

    def tearDown(self):
        # Delete only the uniquely named test graph created by this test.
        self.office.graph.delete()

    def test_real_multihop_context_with_source(self):
        c = self.office.context("launch")
        self.assertEqual(c["decisions"][0]["path"], ["launch", "review", "gate", "release-policy"])
        self.assertIn(["launch", "review", "recovery"], [d["path"] for d in c["dependencies"]])
        self.assertEqual(c["sources"][0]["id"], "release-policy")

    def test_seed_preserves_existing_work(self):
        r = self.office.propose("launch", "reviewer")
        self.assertFalse(self.office.seed()["seeded"])
        self.assertEqual(self.office.get_relay(r["id"])["context_hash"], r["context_hash"])

    def test_unknown_and_query_like_task_are_rejected(self):
        for task in ("missing", "launch'}) MATCH (n) DELETE n //"):
            with self.assertRaises(RelayError):
                self.office.context(task)
        self.assertEqual(self.office.context("launch")["revision"], 1)

    def test_unknown_recipient_cannot_receive_proposal(self):
        with self.assertRaises(RelayError):
            self.office.propose("launch", "missing")

    def test_approval_requires_human_confirmation(self):
        r = self.office.propose("launch", "reviewer")
        with self.assertRaises(RelayError):
            self.office.approve(r["id"])
        self.assertEqual(self.office.get_relay(r["id"])["status"], "pending")

    def test_stale_proposal_is_rejected(self):
        r = self.office.propose("launch", "reviewer")
        self.office.update_decision("cleared", "Policy amendment: recovery evidence accepted.")
        with self.assertRaises(RelayError):
            self.office.approve(r["id"], human_confirmed=True)
        self.assertTrue(self.office.get_relay(r["id"])["stale"])
        self.assertEqual(self.office.get_relay(r["id"])["status"], "pending")

    def test_approved_packet_becomes_unavailable_when_context_changes(self):
        r = self.office.propose("launch", "reviewer")
        self.office.approve(r["id"], human_confirmed=True)
        self.office.update_decision("cleared", "Policy amendment: recovery evidence accepted.")
        with self.assertRaises(RelayError):
            self.office.consume(r["id"], "reviewer")

    def test_only_selected_role_consumes_approved_packet(self):
        r = self.office.propose("launch", "reviewer")
        with self.assertRaises(RelayError):
            self.office.consume(r["id"], "reviewer")
        self.office.approve(r["id"], human_confirmed=True)
        with self.assertRaises(RelayError):
            self.office.consume(r["id"], "builder")
        self.assertEqual(self.office.consume(r["id"], "reviewer")["permissions"],
                         ["read_selected_context", "propose_work"])

    def test_duplicate_approval_is_rejected(self):
        r = self.office.propose("launch", "reviewer")
        self.office.approve(r["id"], human_confirmed=True)
        with self.assertRaises(RelayError):
            self.office.approve(r["id"], human_confirmed=True)

    def test_history_preserves_packet_and_original_source(self):
        r = self.office.propose("launch", "reviewer")
        self.office.update_decision("cleared", "Policy amendment: recovery evidence accepted.")
        old = self.office.get_relay(r["id"])
        self.assertEqual(old["packet"], r["packet"])
        self.assertEqual(old["context_hash"], r["context_hash"])
        current = self.office.context("launch")
        self.assertEqual(current["decisions"][0]["state"], "cleared")
        self.assertEqual(current["sources"][0]["id"], "release-policy-v2")
        history = self.office.query("MATCH (:Document {id:'release-policy-v2'})-[:SUPERSEDES]->(s:Document) RETURN s.id")
        self.assertEqual(history[0][0], "release-policy")

    def test_fresh_proposal_after_mutation_can_be_approved(self):
        self.office.update_decision("cleared", "Policy amendment: recovery evidence accepted.")
        r = self.office.propose("launch", "reviewer")
        self.assertEqual(r["revision"], 2)
        self.assertEqual(self.office.approve(r["id"], human_confirmed=True)["status"], "approved")

    def test_new_process_reads_persisted_packet(self):
        r = self.office.propose("launch", "reviewer")
        self.office.approve(r["id"], human_confirmed=True)
        script = Path(__file__).resolve().parents[1] / "src" / "relay.py"
        run = subprocess.run([sys.executable, str(script), "--graph", self.name,
                              "consume", r["id"], "reviewer"], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout), r["packet"])

    def test_invalid_decision_does_not_change_revision(self):
        for state, text in (("unknown", "text"), ("cleared", " "), ("cleared", "x" * 2001)):
            with self.assertRaises(RelayError):
                self.office.update_decision(state, text)
        self.assertEqual(self.office.context("launch")["revision"], 1)

    def test_mutation_between_context_read_and_proposal_is_rejected(self):
        original = self.office.query

        def raced(statement, **params):
            if "CREATE (r:Relay" in statement:
                self.office.update_decision("cleared", "Policy amendment: recovery evidence accepted.")
            return original(statement, **params)

        self.office.query = raced
        with self.assertRaises(RelayError):
            self.office.propose("launch", "reviewer")

    def test_no_database_means_failure_without_fallback(self):
        # A temporary unused local port is held open without listening.
        import socket
        with socket.socket() as held:
            held.bind(("127.0.0.1", 0))
            with self.assertRaises(Exception):
                unavailable = Office(self.name, port=held.getsockname()[1])
                unavailable.context("launch")


if __name__ == "__main__":
    unittest.main(verbosity=2)
