# ADR 0024 - Administrator Runtime Model Settings

Status: Accepted
Date: 2026-11-21

## Context

ADR 0010 selects model providers and names through environment configuration.
Operators need to tune the three existing LangGraph roles without editing
deployment files or restarting the application. The service compiles one graph
at startup and can run turns concurrently, so shared mutable model instances
would let an edit affect an in-flight turn or another session.

## Decision

- Permit an active application administrator to read and update one global
  configuration for Coordinator, Planner, and Chat through the authenticated
  admin page. Keep the supported providers limited to `openai` and `ollama`.
- Allow each role to set its provider, model identifier, additive system
  guidance, `temperature` (0–2), `top_p` (greater than 0 and at most 1), and
  maximum output tokens (256–16,384). Reject unknown fields, URLs, obvious
  credential prefixes, and out-of-range values. Do not expose API keys,
  provider endpoints, arbitrary model kwargs, or Ollama fallback settings.
- Keep provider credentials, endpoints, model fallbacks, and initial values in
  deployment environment configuration. A role selected as Ollama never calls
  OpenAI. OpenAI errors continue to use the environment-selected Ollama
  fallback with the same generation settings.
- Treat the editable system guidance as supplementary. Place the code-owned
  runtime guard after it in the system message. Keep product policy,
  deterministic plan validation, source checks, graph bounds, and search quotas
  enforced by code and unchanged by admin settings.
- Persist the complete global configuration and revision in the existing
  account database: SQLite for local use and PostgreSQL in Compose. Record
  successful changes with actor, time, action, and changed field names. Do not
  store prompt values in the audit record. Commit settings and audit event in
  one transaction. Require an active administrator for reads and session CSRF
  validation for writes.
- Apply one immutable settings snapshot at the start of each new turn. A running
  turn keeps its snapshot; the next turn reads the latest committed revision.
  Before the new table migration exists, runtime continues to use environment
  settings and admin settings endpoints return `503` with the migration step.
- Require a database backup and paused application writes before the explicit
  migration. Run `uv run python scripts/migrate_runtime_model_settings.py
  --sqlite <auth-database-path>` for SQLite, or run with `--postgres` and the
  configured `GTP_SAVED_TOURS_POSTGRES_*` variables for PostgreSQL. Migration
  does not create or change model credentials.
- When LangSmith tracing is enabled, hide model run inputs and outputs while
  retaining usage and safe metadata needed for account usage reports. Never add
  editable prompt text to custom trace metadata or audit events. Admin UI warns
  that guidance is sent to the selected model provider and must contain no
  credentials or secrets.

## Alternatives Considered

- Keep model settings environment-only: rejected for routine model and prompt
  tuning because each change would require an operator file edit and process
  restart.
- Add a model gateway or credential editor: rejected for this goal. Existing
  typed LangChain adapters already support the two selected providers, while a
  gateway or browser-managed credential would add another secret boundary.
- Mutate shared adapters after each save: rejected because concurrent turns
  could observe partial or cross-turn settings.
- Replace the full code-owned system policy: rejected because an editable
  prompt must not replace deterministic product and security controls.

## Consequences

- The admin API reads durable settings per new turn; database failure returns a
  safe turn failure and preserves the prior plan. The immutable snapshot keeps
  provider/model/hyperparameters consistent within a turn.
- A syntactically valid model identifier may still be unavailable at its
  provider or may have provider-specific parameter limits. Provider errors use
  existing safe failure/fallback behavior; no live provider validation is
  claimed by an admin save.
- The migration is an explicit release prerequisite for admin changes. Until it
  runs, the application remains on its environment settings.
- This decision does not change Tavily routing, LangGraph state, plan
  validation, quotas, account ownership, saved-tour storage, or deployment
  policy.

## Review Triggers

- Add a provider, provider-specific generation control, or editable endpoint.
- Add multiple application instances with a need for settings cache/invalidation
  rather than per-turn database reads.
- Change LangSmith privacy or usage-accounting requirements.
- Expand the admin prompt beyond additive guidance.

## User Amendment — 2026-11-26 — Visible LangSmith Inputs and Outputs

The user explicitly selected visible inputs and outputs for every traced run,
including prompts and answers. This supersedes the blanket hiding decision
above for all providers, including Ollama. Preserve full ordinary message
content and usage/thread metadata while redacting recognized credential fields
and secret patterns. Pattern redaction cannot detect every possible secret;
credentials must remain excluded from model inputs.

Supplementary administrator guidance may appear in model trace inputs. It must
still be excluded from audit events and custom trace metadata. Tracing remains
opt-in through the existing deployment configuration. Previously hidden trace
content cannot be recovered by changing this policy. This decision does not
authorize deployment or change model routing, budgets, or plan validation.
