// Exact query catalog extracted from the submitted Python source.
// Reference only: bind the named parameters from each call site; do not execute this file as one batch.

// src/relay.py:33
MATCH (n) RETURN count(n);

// src/relay.py:35
CREATE
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
          (v)-[:ASSIGNED_TO]->(a), (b)-[:ASSIGNED_TO]->(c);

// src/relay.py:55
MATCH (p:Project {id:'lantern'})-[:HAS_TASK]->(t:Task {id:$task})
          OPTIONAL MATCH path=(t)-[:DEPENDS_ON*0..8]->(dep:Task)
          OPTIONAL MATCH (dep)-[:GOVERNED_BY]->(d:Decision)-[:SUPPORTED_BY]->(s:Document)
          RETURN p.revision, t.name, t.status, dep.id, dep.name, dep.status,
                 [n IN nodes(path) | n.id], d.id, d.text, d.state, d.version,
                 s.id, s.title, s.uri, s.excerpt
          ORDER BY dep.id, d.id, s.id;

// src/relay.py:93
MATCH (p:Project {id:'lantern'})-[:HAS_TASK]->(t:Task {id:$task}),
                (a:Agent {id:$recipient})
          WHERE p.revision = $revision
          CREATE (r:Relay {id:$id, status:'pending', revision:$revision, snapshot:$snapshot,
              packet:$packet, context_hash:$hash, created_at:$created})
          CREATE (r)-[:FOR_TASK]->(t), (r)-[:TO_AGENT]->(a), (p)-[:HAS_RELAY]->(r)
          RETURN r.id;

// src/relay.py:110
MATCH (p:Project {id:'lantern'})-[:HAS_RELAY]->(r:Relay {id:$id})
          RETURN r.id, r.status, r.revision, r.context_hash, r.packet, p.revision;

// src/relay.py:122
MATCH (p:Project {id:'lantern'})-[:HAS_RELAY]->(r:Relay {id:$id})
          WHERE r.status = 'pending' AND r.revision = p.revision
          SET r.status = 'approved', r.approved_at = $now
          RETURN r.id;

// src/relay.py:133
MATCH (p:Project {id:'lantern'})-[:HAS_RELAY]->(r:Relay {id:$id})-[:TO_AGENT]->(a:Agent {id:$agent})
          WHERE r.status = 'approved' AND r.revision = p.revision
          RETURN r.packet;

// src/relay.py:145
MATCH (p:Project {id:'lantern'}), (d:Decision {id:'gate'})-[old:SUPPORTED_BY]->(prior:Document)
          SET d.state=$state, d.text=$text, d.version=d.version+1, p.revision=p.revision+1
          CREATE (source:Document {id:'release-policy-v'+toString(d.version),
            title:'Lantern policy amendment '+toString(d.version),
            uri:'fixture://lantern/policy-amendment/'+toString(d.version), excerpt:$text})
          CREATE (d)-[:SUPPORTED_BY]->(source), (source)-[:SUPERSEDES]->(prior)
          DELETE old
          RETURN p.revision, d.version;

// src/agent.py:68
MATCH (p:Project {id:'lantern'})
       CREATE (r:AgentRun {id:$id, kind:$kind, question:$question, answer:$answer,
          trace:$trace, revision:$revision, model:$model, created_at:$created})
       CREATE (p)-[:HAS_RUN]->(r)
       RETURN r.id;

// src/server.py:21
MATCH (:Project {id:'lantern'})-[:HAS_RELAY]->(r:Relay)
        RETURN r.id ORDER BY r.created_at DESC LIMIT 8;

// src/server.py:23
MATCH (:Project {id:'lantern'})-[:HAS_RUN]->(r:AgentRun)
        RETURN r.id, r.kind, r.answer, r.revision, r.trace, r.model
        ORDER BY r.created_at DESC LIMIT 8;
