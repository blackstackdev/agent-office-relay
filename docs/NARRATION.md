# Agent Office — demo narration

Voice: Kokoro af_heart, American English, speed 0.92. Synthetic stock voice, generated locally.

## Context that survives the handoff

Agent Office is a local agent handoff prototype for Graph Hacks. It carries the reasons behind a task, so the next specialist can resume with current, traceable context.

## Ask the live graph

We are working with a fictional release project. I ask what blocks the release. The local language model reads task context from FalkorDB, then proposes a relay. These are real tool calls against the running database.

## Follow the source path

The release depends on a review. A policy decision governs that review, and the decision points to its source document. The source requires recovery drill evidence. The graph returns both the relationship path and the original excerpt, so the answer can be checked.

## Inspect before approving

The relay is still pending. Its packet records the recipient, selected dependencies, sources, permissions, expected result, and return route. Approval is a separate control. The model can propose this packet, but approval is absent from its tool list.

## Resume in a fresh session

After approval, the review specialist starts a fresh conversation with only the scoped packet. It cites the same policy and proposes what to verify next. One local model serves both roles. This is a verification plan, not a claim that the release work has been executed.

## Change the policy

Now I amend the policy to record that the recovery evidence has been accepted. Saving creates a new source version and advances the graph revision. The previous answer and relay become outdated. Reusing that old packet is blocked.

## Current evidence changes the answer

I ask again. The new context cites the amended source. The policy gate is cleared, while the review task remains open. Clearing a policy gate does not complete a task or approve a release. The next handoff is built from this updated context.

## Persistent, traceable, human controlled

FalkorDB also stores relay snapshots, approvals, source history, and agent runs. Restart testing confirms an approved packet survives a database restart and a fresh process. This local prototype uses fictional data, produces reviewable drafts, and makes no autonomous release actions.
