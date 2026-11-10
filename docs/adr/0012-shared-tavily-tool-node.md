# ADR 0012 - Shared Tavily Tool Node

Status: Accepted
Date: 2026-10-19

## Context

After ADR 0011, the Planner and Chat roles could both call the typed Tavily
provider directly from their agent methods. That kept search behavior split
between roles and made the actual tool boundary less explicit in the compiled
LangGraph architecture. The user requested one graph tool node that both roles
use when a search is needed.

## Decision

- Add one typed LangGraph node named `tavily_tool`. It is the only runtime node
  that invokes `PlaceSearchProvider.search_places`.
- Planner creates a typed `TavilyToolRequest` for grounded plan-change intents.
  Chat creates the same request type from its structured function-call search
  decision. Each request identifies its owner, a query capped at 400 characters
  and a result count capped at eight.
- Route the request to `tavily_tool`, normalize provider results to trusted
  `SourceReference` objects, and return them only to the requesting role. The
  tool node never proposes or modifies the canonical plan.
- Count a search attempt before provider execution, including failed requests.
  Keep the existing maximum of two combined Planner/Chat Tavily attempts per
  turn; Chat may request at most one.
- Emit redacted `tool.tavily.start`, `tool.tavily.success` and
  `tool.tavily.failure` LangSmith events with the requester, result count where
  available and the same session `thread_id`. Do not include search queries,
  conversation history or secrets in these event payloads.
- Keep each graph turn to at most eight graph nodes and one Planner repair.
  Coordinator performs deterministic trip-input validation in its existing
  node, candidate validation performs the bounded repair without an extra graph
  node, and Chat skips search when there is not room for a tool node plus its
  final response node.

## Alternatives Considered

- Let each agent call the provider directly: rejected because it duplicates the
  tool boundary and obscures search in the graph topology.
- Use LangGraph's prebuilt `ToolNode` with native `AIMessage.tool_calls`:
  rejected for this implementation because the runtime uses typed structured
  output providers for both OpenAI and Ollama. A bounded typed graph-node
  request keeps provider and model integrations behind current interfaces.
- Allow a separate Planner tool loop and Chat tool loop with a larger graph
  limit: rejected because the current eight-node bound can be retained with
  explicit requester routing and bounded re-entry.

## Consequences

- The compiled architecture image now shows the actual shared Tavily execution
  node and its return paths.
- LangSmith tool traces identify the request owner and session without copying
  the query into custom event payloads.
- Planner receives search sources before proposing; Chat receives its sources
  before writing the final response. Chat sources remain response-only and
  cannot enter candidate validation.
- A factual Chat request may skip Tavily when the graph has no remaining room;
  in that case Chat must say the current fact could not be verified.
- The maximum remains eight graph nodes, two shared search attempts and one
  repair per turn.

## Review Triggers

- Reconsider use of the prebuilt LangGraph `ToolNode` if model providers gain a
  common tested native tool-call interface.
- Increase the per-turn graph or search bound only after trace measurements
  show a need and the commit/validation path remains bounded.
- Change owner routing or source handoff only with tests proving search results
  cannot leak into another role or mutate plan state.

## Supersedes

This ADR supersedes ADR 0011 where it describes the app calling the provider
directly or says Chat search adds no graph node. ADR 0011's session-only history,
summary bounds, Chat search policy, shared search limit and source-isolation
decisions remain accepted.
