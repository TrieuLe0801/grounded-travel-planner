# ADR 0011 - Bounded Session Context And Optional Chat Search

Status: Accepted
Date: 2026-10-19

## Context

The webapp kept the canonical itinerary in its session but did not preserve the
active conversation for the Coordinator. Users could refer to a prior turn
without that context being available to route or answer the request. At the
same time, Chat could not look up current facts when responding to ordinary
questions. Passing the full transcript to each model role would grow prompts
without a bound and repeat citation snippets that do not help routing.

## Decision

- Keep the active conversation in the existing in-memory browser session only.
  Keep at most 12 user/assistant messages, each no longer than the API's 4,000
  character input bound. Session reset starts a new empty transcript; page
  reload hydrates it from the same session endpoint.
- Give Coordinator the prior summary (maximum 1,200 characters) and at most
  eight recent messages (maximum 600 characters each). Omit stored citation
  snippets from the Coordinator prompt. Ask Coordinator for a concise updated
  handoff summary capped at 1,200 characters.
- Give Planner and Chat that summary plus only the task-specific current
  request, intent and itinerary context. Do not pass the raw transcript to
  those roles.
- Allow Chat to use its structured function-call output to request at most one
  Tavily query when current factual information is needed. The shared graph
  tool node executes the typed provider call under ADR 0012; Chat does not
  receive an arbitrary tool executor and cannot mutate the plan.
- Share the existing maximum of two Tavily attempts per turn across Planner
  and Chat. Chat search results are response-only citations built from actual
  provider results and never enter the candidate or validation path.
- Record redacted search events with result counts and the session `thread_id`.
  ADR 0012 defines their names and owner-specific payload. Do not include raw
  transcript, search query or secrets in these events.
- If no usable Chat search sources are returned, instruct Chat to say current
  facts could not be verified instead of guessing or claiming verification.

## Alternatives Considered

- Pass the complete transcript to every role: rejected because prompt size
  would grow and repeat content unrelated to the current task.
- Persist transcript in a database or LangSmith: rejected because app state is
  session-only and traces are observability data.
- Give Chat an unbounded native tool loop: rejected because it would make search
  usage and graph work difficult to bound and would allow unnecessary calls.
- Let Chat search change plan state: rejected because all plan proposals and
  commits remain owned by Planner and deterministic validation.

## Consequences

- References such as “dựa vào lịch trình đã đề xuất” can be resolved using the
  active session plan and Coordinator summary.
- Older conversation messages age out of the transcript, while the rolling
  summary carries forward user constraints and current context.
- Chat can cite a current Tavily result for a factual response without changing
  the canonical plan; ADR 0012 defines the shared graph tool node.
- Search-call counters and LangSmith events include Chat's attempted call.
- Session restart or expiry still drops conversation and summary; this is
  intentional and consistent with the session-only product boundary.

## Review Triggers

- Raise the 12-message, 8-message prompt, 600-character or 1,200-character
  limits only after measuring token usage and verifying provider context limits.
- Reconsider the two-call shared search cap if live traces show a measurable
  need, while retaining an explicit per-turn bound.
- Add durable history only after a separate user decision changes the
  session-only privacy and storage boundary.

## Supersedes

This ADR amends ADR 0009 only where it says Planner is the sole role that may
search. Planner remains the only role that proposes plan changes; Chat may
search only to answer the user and cannot alter the plan. All other ADR 0009
decisions remain in force. ADR 0012 supersedes the direct provider-call
mechanism described here and defines the shared graph node.
