# Local model comparison and trace visibility — 2026-11-26

## Goal and decision

The user requested visible LangSmith prompts and answers for every traced run,
and a local model balancing speed with Vietnamese/English quality. The target
is Apple M1 with 16 GiB RAM. No commit, push, or deployment was requested.

Recommend `qwen3:8b` as the next **Chat-only evaluation candidate**. Its sampled
Vietnamese and English answers followed the three-sentence instruction and
expressed uncertainty more accurately than the other candidates. It is slower
than the current 4B model, but uses less storage than 9B and showed lower
median chat latency than 9B. This is a small synthetic comparison, not a general quality
ranking or approval for production. None of the candidates passed every
schedule check; do not promote any as a Planner replacement on this evidence.
Runtime model settings remain unchanged.

## Method

Ollama 0.40.16; LangChain ChatOllama; `reasoning=False`, `temperature=0`,
`num_ctx=4096`, `num_predict=768`. Each model received a warmup followed by
two repetitions of four tasks: Vietnamese chat, English chat, Vietnamese JSON
schedule, and English JSON schedule. Calls had a 90-second deadline and no
implicit retry. Models were unloaded between groups. Benchmark tracing was
disabled. Prompts, responses, model digests, timings, settings, and memory
snapshots are retained in the [raw evidence](2026-11-26-local-model-comparison.json).

The schedule used invented places and source IDs. Independent expected times:
Vườn Sen 09:00–09:45; 15-minute travel; Bảo tàng Mây 10:00–11:00. Names and
source IDs must remain exact. Schema success alone does not establish schedule
correctness. Chat required three sentences, the requested language, uncertainty
about opening hours, and a direction to check official sources.

## Results

| Installed artifact | Disk size (decimal GB) | Median chat seconds | Median JSON seconds | Correct schedules |
|---|---:|---:|---:|---:|
| qwen3.5:4b-mlx, MLX nvfp4 | 3.97 | 5.58 | 9.34 | 2/4 |
| qwen3:8b, GGUF Q4_K_M | 5.23 | 8.45 | 14.99 | 0/4 |
| qwen3.5:9b, MLX | 7.64 | 9.41 | 10.40 | 1/4 |

All 24 measured responses were nonempty, had no returned reasoning content,
and ended with `done_reason=stop`. All 12 schedule responses parsed against
the schema. Correctness remained inadequate:

- 4B repeated a 105-minute visit where 45 minutes was requested in Vietnamese.
  Its Vietnamese prose used only two sentences and awkward wording such as
  “lịch khai trương”. Both English schedules passed.
- 8B prose was clearer in both languages and followed the sentence constraint.
  All four schedules failed duration/travel constraints; some exceeded closing
  hours. Clear prose did not imply sound schedule arithmetic.
- 9B also confused duration, arrival, and opening constraints; only one schedule
  passed. Its Vietnamese prose described unverified hours as already inaccurate,
  overstating what is known. Increased size did not resolve the observed issues.

These compare actual installed artifacts, not equal quantization or identical
backends. The host was already swapping: approximately 7.7–8.0 GB used around
4B/8B, and 6.0–9.5 GB around 9B. Background load and cache state were not
controlled. Two repetitions do not establish statistical significance, sustained
throughput, long-context behavior, actual trip quality, or deployed latency.
The 9B download is the observed 7.64 GB MLX artifact, not an assumed Q4 variant.

## Trace implementation and verification

ADR 0024's blanket input/output hiding was the direct cause of missing content.
The client now retains ordinary inputs and outputs using the SDK anonymizer to
redact serialized credential fields and recognizable `sk-`, `tvly-`, and Bearer
patterns. This preserves complete messages, UUID thread IDs, account hashes,
source IDs, and usage metrics. Pattern matching cannot recognize every secret;
credentials must not enter model inputs.

Custom events also assumed `Client.create_run()` returned a run object, but the
installed SDK returns `None`. Events now allocate their own UUID and update
outputs and completion time using it. The tester reproduced the original
missing update and verified the regression test.

Independent offline checks: 50 focused tests passed; full suite 301 passed,
one optional PostgreSQL test skipped because opt-in settings were absent.
isort, Black, flake8, Ruff, and diff checks passed. The application-adapter smoke is recorded below. Live trace readback passed all 13 checks. No frontend/browser, full app, Tavily, or deployment acceptance is
claimed by this experiment.

## Application-adapter smoke

The actual `OllamaStructuredChatModel` ran Qwen3 8B with the existing Chat
output cap of 2,048 tokens, temperature zero, and no forced context size. Both
Vietnamese and English responses passed the answer schema and three-sentence
constraint, taking 15.452 and 7.462 seconds respectively. These single-call
latencies are separate from the paired benchmark above. The English answer
added an unsupported generic duration range (“a few hours to a full day”).
Therefore the smoke proves adapter execution, not factual-quality acceptance.
The raw evidence includes settings, prompts, responses, and elapsed times.

## Live LangSmith readback

A synthetic traced root invoked the actual Ollama adapter with Qwen3 8B.
After flushing, the tester read the root and LLM child from LangSmith. All
13 checks passed: visible root and child inputs/outputs; recognized synthetic
credentials redacted; identical UUID thread metadata retained; Ollama provider,
model, and token usage present; custom event outputs and completion time saved.
Synthetic credentials were used only at the root, not passed to the model.

The [verified trace](https://smith.langchain.com/o/68932dd2-cadf-4d37-a623-c569afd4fa5e/projects/p/352b6d59-4700-4ef9-b27e-60ae81bf0722/r/01a21874-54a4-76b2-b0e9-db22eba55b82?poll=true) and custom event
`28f79ee8-bbd2-41cc-81d8-bf2a2cc0fb06` establish this direct integration only.
They do not establish a deployed application turn or all runtime role/tool flows.
The SDK emitted deprecation warnings for readback helpers, not test failures.
Previously hidden trace content cannot be recovered. App deployment and runtime
model selection remain unchanged; no commit or push was performed.

## Subsequent user decision

After reviewing these results, the user explicitly selected `qwen3:8b` to
replace the current local model. Read-only inspection identified the existing
selection as the global Ollama fallback (`qwen3.5:4b-mlx`) in the deployment
`.env`; all primary roles use OpenAI, there are no per-role fallback overrides,
and the administrator settings table has no global override. Therefore the
requested change replaces only the fallback model, preserving primary routing.
The selection is the user's preference despite the benchmark limitations; it
does not convert the failed schedule checks into quality acceptance.

## Activation evidence

The deployment environment's single global Ollama fallback changed from
`qwen3.5:4b-mlx` to `qwen3:8b`. A same-image, app-only Compose recreation
activated it. The running app is healthy and public `/api/auth/me` returned
HTTP 200. Container environment confirms `qwen3:8b`; all primary role models
and providers match the recorded prechange state. Image ID remained
`sha256:799ff692994ebc0088c36cf4d8406c0a416844dfe1d6e511225770d015332000`.
The database container was not included in the command. Its ID differed from
an earlier baseline snapshot, but its creation time preceded the app recreation
by about seven minutes, so this operation did not cause that change. The
`.env` backup is private and outside Git. Recreating the app cleared unsaved
session state. The earlier LangSmith source fix remains in this development
checkout and was not rolled out by the same-image configuration change.
