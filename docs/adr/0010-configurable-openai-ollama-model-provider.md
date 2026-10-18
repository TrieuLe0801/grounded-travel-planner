# ADR 0010 - Configurable OpenAI and Ollama Model Provider

Status: Accepted
Date: 2026-10-18

## Context

ADR 0004 lists a provider change as a review trigger. The sightseeing runtime
already has typed structured-model boundaries and three role-specific model
names, but it previously constructed only OpenAI adapters. The user needs a
local lightweight option when an OpenAI API call is unsuitable or unavailable.

## Decision

Select the legacy global provider explicitly with `GTP_MODEL_PROVIDER`, accepting
only `openai` (the default) and `ollama`. `GTP_COORDINATOR_PROVIDER`,
`GTP_PLANNER_PROVIDER` and `GTP_CHAT_PROVIDER` may override it per role and use
the same accepted values. Read every role model from the environment:
`GTP_COORDINATOR_MODEL`, `GTP_PLANNER_MODEL`, and `GTP_CHAT_MODEL`. Empty names
and unsupported providers fail during configuration parsing.

OpenAI keeps its current `ChatOpenAI` adapter and defaults: `gpt-5.5` for
Coordinator and `gpt-5.4-mini` for Planner and Chat. Ollama uses a separate
typed `ChatOllama` adapter with LangChain structured output, common system/human
messages and trace metadata. It never falls back to OpenAI.

`OLLAMA_BASE_URL` continues to control an app run directly on the host; an empty
value lets ChatOllama use its provider default. Compose uses the separate
`GTP_COMPOSE_OLLAMA_BASE_URL`, defaulting to
`http://host.docker.internal:11434` so the app container can reach a host
Ollama process. The opt-in Compose `ollama` profile requires the explicit
override `http://ollama:11434`; it has a persistent model volume and a one-shot
initializer that pulls the whitespace-separated `OLLAMA_PULL_MODELS` list,
defaulting to `qwen2.5:3b`. Model weights are never built into the application
image and Ollama does not start in the default Compose workflow.

## Consequences

- Each runtime role uses its resolved provider and model, while preserving the
  legacy global-provider behavior when no override is set.
- Tests can verify provider routing and structured calls without network access.
- Native `qwen2.5:3b` has passed both all-local and active mixed-role
  (OpenAI `gpt-5.5` Coordinator, Ollama `qwen2.5:3b` Planner/Chat) create-trip
  smokes. The earlier `qwen3:4b` mixed smoke remains historical evidence.
  Chat-edit intents and the Compose profile still need separate live checks.
