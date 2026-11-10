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

At acceptance, OpenAI used the `ChatOpenAI` adapter and defaults of `gpt-5.5`
for Coordinator, `gpt-5.4-mini` for Planner, and `gpt-4.1` for Chat. That was
the default `.env.example` configuration when no local model was being served;
the Planner default is superseded by the amendment below.
Ollama uses a separate typed `ChatOllama` adapter with LangChain structured
output, common system/human messages and trace metadata. It never falls back to
OpenAI.

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
- A local role is selected only by explicit environment configuration. If its
  Ollama server is unavailable, the turn returns a safe failure instead of
  making an unexpected OpenAI API call.
- Tests can verify provider routing and structured calls without network access.
- Native `qwen2.5:3b` has passed both all-local and active mixed-role
  (OpenAI `gpt-5.5` Coordinator, Ollama `qwen2.5:3b` Planner/Chat) create-trip
  smokes. The earlier `qwen3:4b` mixed smoke remains historical evidence.
  Chat-edit intents and the Compose profile still need separate live checks.

## User Amendment — 2026-10-26 — OpenAI Failure Fallback

When a role is configured for OpenAI and its API call fails, try the same
structured request once with the local Ollama model selected by
`GTP_OLLAMA_FALLBACK_MODEL` (default `qwen2.5:3b`), with optional
`GTP_COORDINATOR_OLLAMA_FALLBACK_MODEL`, `GTP_PLANNER_OLLAMA_FALLBACK_MODEL`
and `GTP_CHAT_OLLAMA_FALLBACK_MODEL` overrides. Preserve the prompt, output
schema and turn trace metadata. This is a one-way failover: a role explicitly
configured for Ollama still never calls OpenAI. Invalid structured output and
application errors are not provider availability failures and do not trigger
failover. If Ollama is unavailable or also fails, retain the existing safe
failure and previous-plan behavior. The fallback does not add graph steps,
search calls or repair attempts, and all candidate plans still require normal
validation before commit.

The local model must be installed and reachable from the app environment.
The default Compose path remains OpenAI-first and does not start Ollama by
itself; its existing host endpoint or opt-in Ollama profile can serve the
fallback model.

## Planner Default Amendment — 2026-10-27

The Planner OpenAI default is `gpt-6.1-terra`, superseding the earlier
`gpt-5.4-mini` default in this ADR and ADR 0009. The user requested a model
with a larger context window and better latency for planning. OpenAI documents
1,050,000 context tokens for Terra versus 400,000 for GPT-5.4 Mini. Planner
sets `reasoning_effort="none"` to favor latency and uses JSON-schema
structured output through Chat Completions, because Terra tool calling
requires the Responses API. The app's Tavily request remains a typed graph
request, not a model-native tool call. Coordinator, Chat, role overrides,
validation and the one-attempt Ollama fallback are unchanged. A small
model-only live structured call verified account access; no full Planner
latency improvement is claimed.
Model specifications: `https://developers.openai.com/api/docs/models/gpt-6.1-terra`
and `https://developers.openai.com/api/docs/models/gpt-5.4-mini`.

## User Amendment — 2026-10-27 — Any OpenAI API Error

For every role configured for OpenAI, any exception from the OpenAI SDK's
`OpenAIError` family triggers the one Ollama attempt immediately, including
HTTP 400 and other API status errors. This supersedes the prior fallback's
availability-only error filter. Keep local schema validation and application
errors outside that catch. The same prompt, schema and trace metadata are used;
explicit Ollama roles remain Ollama-only. Both-provider failure and plan
validation retain the existing safe behavior.

## User Amendment — 2026-10-27 — Native Apple MLX Fallback

For this Mac's local deployment, use native macOS Ollama with
`qwen3.5:4b-mlx` through `host.docker.internal` as the OpenAI fallback. The
user also requested removing the previous `qwen2.5:3b` model after the MLX
path is verified.
The repository's cross-platform fallback default remains separate from this
host-specific deployment choice. Do not route the Apple MLX model through the
Linux Ollama container, which lacks the Mac's GPU passthrough.

## User Amendment — 2026-10-27 — Model Names Only in Environment

Do not embed model identifiers in runtime code. Read Coordinator, Planner,
Chat, Ollama fallback and JSON-schema-mode model names from environment
variables. `GTP_COORDINATOR_MODEL`, `GTP_PLANNER_MODEL`, `GTP_CHAT_MODEL` and
`GTP_OLLAMA_FALLBACK_MODEL` are required by live service construction;
`GTP_OPENAI_JSON_SCHEMA_MODELS` lists model identifiers that need JSON-schema
structured output. Unit fixtures use synthetic names and do not define runtime
defaults. Missing required model variables fail configuration instead of
silently selecting a model.
