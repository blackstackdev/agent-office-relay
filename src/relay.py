"""Graph-backed relay feasibility tool. No LLM or autonomous agents yet."""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from uuid import uuid4

from falkordb import FalkorDB

VERSION = "0.2.1"


class RelayError(Exception):
    pass


class Office:
    def __init__(self, graph_name=None, port=None):
        graph_name = graph_name or os.getenv("RELAY_GRAPH", "agent_office_relay")
        if not re.fullmatch(r"(?:agent_office_relay|relay_test_[a-f0-9]+)", graph_name):
            raise RelayError("Use the demo graph or an isolated relay_test_<hex> graph.")
        self.db = FalkorDB(host="127.0.0.1", port=port or int(os.getenv("RELAY_DB_PORT", "6387")),
                           socket_connect_timeout=3, socket_timeout=5)
        self.graph = self.db.select_graph(graph_name)

    def query(self, statement, **params):
        return self.graph.query(statement, params=params).result_set

    def seed(self):
        if self.query("MATCH (n) RETURN count(n)")[0][0]:
            return {"seeded": False, "reason": "Graph already contains data; preserved."}
        self.query("""CREATE
          (p:Project {id:'lantern', name:'Lantern release', revision:1}),
          (t:Task {id:'launch', name:'Publish the Lantern release', status:'todo'}),
          (v:Task {id:'review', name:'Complete release review', status:'todo'}),
          (b:Task {id:'recovery', name:'Run the recovery drill', status:'todo'}),
          (d:Decision {id:'gate', text:'Recovery drill evidence is required before release review.',
                       state:'blocking', version:1}),
          (s:Document {id:'release-policy', title:'Lantern release policy',
             uri:'fixture://lantern/release-policy#section-2',
             excerpt:'Section 2: Complete a recovery drill and attach the evidence before review.'}),
          (a:Agent {id:'reviewer', name:'Review specialist'}),
          (c:Agent {id:'builder', name:'Build specialist'}),
          (p)-[:HAS_TASK]->(t), (p)-[:HAS_TASK]->(v), (p)-[:HAS_TASK]->(b),
          (t)-[:DEPENDS_ON]->(v), (v)-[:DEPENDS_ON]->(b),
          (v)-[:GOVERNED_BY]->(d), (d)-[:SUPPORTED_BY]->(s),
          (v)-[:ASSIGNED_TO]->(a), (b)-[:ASSIGNED_TO]->(c)
        """)
        return {"seeded": True, "fixture": "Fictional Lantern team"}

    def context(self, task_id):
        rows = self.query("""
          MATCH (p:Project {id:'lantern'})-[:HAS_TASK]->(t:Task {id:$task})
          OPTIONAL MATCH path=(t)-[:DEPENDS_ON*0..8]->(dep:Task)
          OPTIONAL MATCH (dep)-[:GOVERNED_BY]->(d:Decision)-[:SUPPORTED_BY]->(s:Document)
          RETURN p.revision, t.name, t.status, dep.id, dep.name, dep.status,
                 [n IN nodes(path) | n.id], d.id, d.text, d.state, d.version,
                 s.id, s.title, s.uri, s.excerpt
          ORDER BY dep.id, d.id, s.id
        """, task=task_id)
        if not rows:
            raise RelayError("Task not found in the demo project.")
        result = {"project": "lantern", "revision": rows[0][0], "task_id": task_id,
                  "task": rows[0][1], "status": rows[0][2], "dependencies": [],
                  "decisions": [], "sources": []}
        for row in rows:
            if row[3] and row[3] != task_id:
                item = {"id": row[3], "name": row[4], "status": row[5], "path": row[6]}
                if item not in result["dependencies"]:
                    result["dependencies"].append(item)
            if row[7]:
                item = {"id": row[7], "text": row[8], "state": row[9], "version": row[10],
                        "path": row[6] + [row[7], row[11]]}
                if item not in result["decisions"]:
                    result["decisions"].append(item)
                source = {"id": row[11], "title": row[12], "uri": row[13], "excerpt": row[14]}
                if source not in result["sources"]:
                    result["sources"].append(source)
        return result

    def propose(self, task_id, recipient):
        context = self.context(task_id)
        snapshot = json.dumps(context, sort_keys=True, ensure_ascii=False)
        relay_id = uuid4().hex
        packet = {"task": context["task"], "purpose": "Resume work using the current source-linked context.",
                  "recipient": recipient, "context": context,
                  "permissions": ["read_selected_context", "propose_work"],
                  "expected_result": "Return evidence and a proposed next step for human review.",
                  "return_route": "Human approval queue"}
        rows = self.query("""
          MATCH (p:Project {id:'lantern'})-[:HAS_TASK]->(t:Task {id:$task}),
                (a:Agent {id:$recipient})
          WHERE p.revision = $revision
          CREATE (r:Relay {id:$id, status:'pending', revision:$revision, snapshot:$snapshot,
              packet:$packet, context_hash:$hash, created_at:$created})
          CREATE (r)-[:FOR_TASK]->(t), (r)-[:TO_AGENT]->(a), (p)-[:HAS_RELAY]->(r)
          RETURN r.id
        """, task=task_id, recipient=recipient, revision=context["revision"], id=relay_id,
            snapshot=snapshot, packet=json.dumps(packet, ensure_ascii=False),
            hash=hashlib.sha256(snapshot.encode()).hexdigest(),
            created=datetime.now(timezone.utc).isoformat())
        if not rows:
            raise RelayError("Recipient not found, or graph changed during proposal; refresh context.")
        return self.get_relay(relay_id)

    def get_relay(self, relay_id):
        rows = self.query("""MATCH (p:Project {id:'lantern'})-[:HAS_RELAY]->(r:Relay {id:$id})
          RETURN r.id, r.status, r.revision, r.context_hash, r.packet, p.revision""", id=relay_id)
        if not rows:
            raise RelayError("Relay not found.")
        row = rows[0]
        return {"id": row[0], "status": row[1], "revision": row[2], "context_hash": row[3],
                "packet": json.loads(row[4]), "stale": row[2] != row[5]}

    def approve(self, relay_id, human_confirmed=False):
        if not human_confirmed:
            raise RelayError("Explicit human confirmation is required.")
        # Revision match and state mutation happen in one graph write query.
        rows = self.query("""
          MATCH (p:Project {id:'lantern'})-[:HAS_RELAY]->(r:Relay {id:$id})
          WHERE r.status = 'pending' AND r.revision = p.revision
          SET r.status = 'approved', r.approved_at = $now
          RETURN r.id
        """, id=relay_id, now=datetime.now(timezone.utc).isoformat())
        if not rows:
            raise RelayError("Approval rejected: missing, already handled, or stale relay. Create a fresh proposal.")
        return self.get_relay(relay_id)

    def consume(self, relay_id, recipient):
        rows = self.query("""
          MATCH (p:Project {id:'lantern'})-[:HAS_RELAY]->(r:Relay {id:$id})-[:TO_AGENT]->(a:Agent {id:$agent})
          WHERE r.status = 'approved' AND r.revision = p.revision
          RETURN r.packet
        """, id=relay_id, agent=recipient)
        if not rows:
            raise RelayError("Packet unavailable: wrong recipient, approval missing, or context changed.")
        return json.loads(rows[0][0])

    def update_decision(self, state, text):
        if state not in ("blocking", "cleared") or not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000:
            raise RelayError("Decision requires blocking/cleared state and 1–2000 characters.")
        rows = self.query("""
          MATCH (p:Project {id:'lantern'}), (d:Decision {id:'gate'})-[old:SUPPORTED_BY]->(prior:Document)
          SET d.state=$state, d.text=$text, d.version=d.version+1, p.revision=p.revision+1
          CREATE (source:Document {id:'release-policy-v'+toString(d.version),
            title:'Lantern policy amendment '+toString(d.version),
            uri:'fixture://lantern/policy-amendment/'+toString(d.version), excerpt:$text})
          CREATE (d)-[:SUPPORTED_BY]->(source), (source)-[:SUPERSEDES]->(prior)
          DELETE old
          RETURN p.revision, d.version
        """, state=state, text=text.strip())
        if not rows:
            raise RelayError("Seed the fictional project first.")
        return {"revision": rows[0][0], "decision_version": rows[0][1]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--graph", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed")
    context = sub.add_parser("context")
    context.add_argument("task")
    propose = sub.add_parser("propose")
    propose.add_argument("task")
    propose.add_argument("recipient")
    show = sub.add_parser("show")
    show.add_argument("relay")
    approve = sub.add_parser("approve")
    approve.add_argument("relay")
    approve.add_argument("--human-confirm", action="store_true")
    consume = sub.add_parser("consume")
    consume.add_argument("relay")
    consume.add_argument("recipient")
    update = sub.add_parser("update-decision")
    update.add_argument("state", choices=["blocking", "cleared"])
    update.add_argument("text")
    args = parser.parse_args()
    try:
        office = Office(args.graph)
        actions = {"seed": lambda: office.seed(), "context": lambda: office.context(args.task),
                   "propose": lambda: office.propose(args.task, args.recipient),
                   "show": lambda: office.get_relay(args.relay),
                   "approve": lambda: office.approve(args.relay, args.human_confirm),
                   "consume": lambda: office.consume(args.relay, args.recipient),
                   "update-decision": lambda: office.update_decision(args.state, args.text)}
        print(json.dumps(actions[args.command](), indent=2, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"error": str(exc), "database_required": True}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
