# Follow-up: Re-enable verbatim `agent_trace` (backend, memory-safe)

Status: **scoped, NOT implemented.** This is the deferred backend half of the
agent-trace UI work (`feat/agent-trace-ui`). Do not build until the memory-safe
approach below is in place — a naive re-enable already crashed twice
(`6d8f657` add lightweight trace → `185abce` revert "still causing crashes" →
`7fba18a` disable `scratchpad.to_dict()` — memory crash on Render).

## Current state

- The agentic endpoint returns `agent_trace = {"note": "Agent trace disabled to
  reduce memory usage"}` (`backend/agents/orchestrator.py:648`).
- The full serializer `SharedMemory.to_dict()` and a `create_lightweight_trace()`
  exist (`backend/agents/shared_memory.py`) but are not called into the response;
  enabling them is what OOM-crashed the Render instance.
- The **frontend panel already shipped works without this** — it reconstructs the
  flow from the real response fields (`iterations`, `confidence`,
  `confidence_improvements`, and per-violation `judge_id`/`focus_area`/`reasoning`/
  `confidence`/`abstain`/grounding). This follow-up only adds the *granular* trace
  (orchestrator routing-decision text, per-step researcher log, exact per-judge
  reflection re-runs) that the UI cannot currently show.

## Why it crashed (likely)

`SharedMemory` accumulates full plan/result/reflection objects per agent per
iteration; `to_dict()` deep-serializes all of it (including full prompts,
retrieved chunks, and every reflection) into one JSON blob held in memory
alongside the response — on a small Render instance, across concurrent jobs, that
spikes RSS past the limit.

## Memory-safe scope (when picked up)

Build a **bounded, projection-only** trace — never serialize the whole scratchpad:

1. **Cap and truncate.** Per agent: keep only `{name, focus_area, decision,
   confidence, abstain}` + reasoning **truncated** to ~300 chars. Drop raw prompts
   and retrieved-chunk text entirely (the UI doesn't need them).
2. **Bound the timeline.** `iteration_history` and `low_confidence_flags` capped to
   the last N (e.g. 20) entries; no nested per-iteration full payloads.
3. **No deep copies.** Build the trace dict by reading scalar fields directly; avoid
   `copy.deepcopy` and avoid holding both the scratchpad and its serialized form.
4. **Opt-in + size guard.** Only assemble when `include_agent_trace=true`; if the
   projected trace exceeds a hard byte cap (e.g. 64KB), drop the heaviest section
   and set `agent_trace.truncated = true` rather than returning it whole.
5. **Free early.** `scratchpad.clear()` immediately after projecting.

## Verify before shipping

- Load-test the agentic endpoint with `include_agent_trace=true` under concurrency
  on a Render-sized instance; watch RSS stays within limit (the original failure
  mode).
- Confirm the projected trace shape matches what the UI expects, then extend
  `renderAgentReasoning()` to render the granular fields (routing text, per-step
  log) **only when present** — same hard rule as the shipped panel: real data only,
  no fabrication.

## Out of scope for the shipped UI ticket

The frontend panel (`feat/agent-trace-ui`) is complete and honest without this.
This document exists so the granular trace can be restored later as its own
branch, with the memory fix as the gating prerequisite.
