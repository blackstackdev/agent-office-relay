# Architecture and authority

React browser -> local Python HTTP server -> official FalkorDB client -> FalkorDB.
The server invokes local Ollama at 127.0.0.1:11434. App and graph bind only to
127.0.0.1:4176 and 127.0.0.1:6387. Docker volume agent-office-relay_relay-data
uses append-only persistence with appendfsync always.

Coordinator tool list: get_task_context and propose_relay. The workflow is bounded
to one selected fictional task, at most five model turns, six calls and one proposal.
One missing-plan reminder is allowed. Missing investigation, malformed tool
arguments, unknown tools, changed revision or invalid source references fails.

After proposal, the model returns a JSON-schema-constrained summary, next_check
and source_ids. The app validates IDs against the current context and renders
those references and the actual task/recipient/status from the saved packet.
This prevents free-form citation formatting and invented handoff identity from
silently replacing canonical fields. Summary semantics still require review.

Approval and policy editing are separate human HTTP/CLI operations, absent from
the model tools. The specialist first consumes a current approved packet, then
starts a new conversation with that packet only. It has no execution tools.
The same model serves both roles; there are no independent agent workers.

One inference runs at a time. Local HTTP checks reject unrelated Origins,
unrecognized Host headers, missing approval confirmation and oversized requests.
These checks do not replace authentication. This is a trusted-local demonstrator,
not a service for arbitrary users. Direct admin writes, cyclic/large imports,
concurrent seeding, backup/restore and tenant isolation are outside its contract.

Optional recording isolation: RELAY_GRAPH may select agent_office_relay or an
isolated relay_test_<hex> graph. Unknown graph names are rejected. Tests always
use their own explicit random graph names; recording does not reset default data.
