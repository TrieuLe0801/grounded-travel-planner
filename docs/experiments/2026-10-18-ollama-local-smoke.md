# Native Ollama Local Smoke

Date: 2026-10-18
Status: Passed on the host and through the Compose app; internal Ollama profile not run

## Target environment

- macOS 26.6.2 on arm64 (Mac M1)
- Ollama 0.9.0, listening on `127.0.0.1:11434`
- Metal reported 11.8 GiB available inference memory
- Model: `qwen2.5:3b` (downloaded locally; reported size 1.9 GB)
- Model: `qwen3:4b` (downloaded locally; reported size 2.5 GB and 5.1 GB
  loaded on the GPU during the mixed-provider smoke)

The internal Compose Ollama profile passed static configuration validation but
was not built or started. Its app endpoint defaults through
`GTP_COMPOSE_OLLAMA_BASE_URL` to `http://host.docker.internal:11434`; the
opt-in internal Ollama profile requires the explicit
`http://ollama:11434` override.

## Configuration

The process environment selected the same local model for every runtime role:

```dotenv
GTP_MODEL_PROVIDER=ollama
GTP_COORDINATOR_MODEL=qwen2.5:3b
GTP_PLANNER_MODEL=qwen2.5:3b
GTP_CHAT_MODEL=qwen2.5:3b
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

No OpenAI fallback was enabled.

## Results

1. `OllamaStructuredChatModel` returned a valid `ChatResponse` through
   LangChain structured output.
2. A Vietnamese request to create a one-day Hue itinerary committed successfully:
   - two itinerary entries, revision 1;
   - five graph steps;
   - one Tavily search and no repair;
   - no validation issues;
   - Coordinator, Planner and Chat all reported `qwen2.5:3b`.
3. LangSmith returned 25 matching root/child runs for the smoke's `thread_id`;
   every returned run carried that same value.

## Mixed-provider result

The requested role assignment passed on the native host:

```dotenv
GTP_MODEL_PROVIDER=openai
GTP_COORDINATOR_PROVIDER=openai
GTP_PLANNER_PROVIDER=ollama
GTP_CHAT_PROVIDER=ollama
GTP_COORDINATOR_MODEL=gpt-5.5
GTP_PLANNER_MODEL=qwen3:4b
GTP_CHAT_MODEL=qwen3:4b
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

1. `qwen3:4b` returned a non-empty `ChatResponse` through the typed structured
   adapter.
2. The Vietnamese one-day Hue request with thread ID
   `mixed-provider-hue-smoke-20261018` committed successfully:
   - four itinerary entries, revision 1;
   - five graph steps;
   - one Tavily search and no repair;
   - no validation issues;
   - Coordinator: OpenAI `gpt-5.5`; Planner and Chat: Ollama `qwen3:4b`.
3. LangSmith returned 25 matching root/child runs (seven root and 18 child) for
   that thread ID; every returned run carried the same value.

The smoke does not exercise chat edits or the internal Docker Compose profile.

## Compose app to native Ollama endpoint

The Compose app originally received `OLLAMA_BASE_URL=http://127.0.0.1:11434`.
That address resolves inside the app container, where no Ollama server listens,
so Planner returned its safe connection-refused response and preserved the
previous plan. Host-native Ollama was reachable from the container at
`http://host.docker.internal:11434`.

After setting `GTP_COMPOSE_OLLAMA_BASE_URL` to that host address and recreating
the app container:

1. The app reached healthy status on `127.0.0.1:8503`.
2. `qwen3:4b` returned a non-empty structured response through the app
   container's configured endpoint.
3. A fresh HTTP API session committed a Vietnamese one-day Hue plan: four
   entries, one Tavily search, no repair and no validation issues.

The internal `ollama` Compose profile remains unrun.
