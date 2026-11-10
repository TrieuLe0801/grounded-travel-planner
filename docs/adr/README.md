# Architecture Decision Records

The active product/runtime scope is defined by ADR 0004 and the current
[charter](../project-charter.md). Preserve superseded records as history.

| Record | Status |
|---|---|
| [0001 — Python development tooling](0001-python-development-tooling.md) | Accepted for tooling; runtime references updated by 0004 |
| [0002 — Three-week POC](0002-three-week-poc-scope.md) | Superseded by 0004 |
| [0003 — Previous POC UI](0003-streamlit-poc-ui.md) | Superseded by 0004 |
| [0004 — City sightseeing runtime](0004-city-sightseeing-two-agent-runtime.md) | Accepted; partial updates in ADR 0009 |

Use sequential filenames. Include status, context, decision, alternatives,
consequences and review triggers in each new record.

Current runtime decisions: ADR 0009 defines Coordinator-routed chat and trip
extension; ADR 0010 defines model-provider configuration; ADR 0011 defines
bounded session context and optional Chat search; ADR 0012 defines the shared
Tavily graph tool node; ADR 0013 defines the session-scoped bilingual UI locale.
ADR 0014 permits only explicitly saved, validated tour snapshots. ADR 0015
moves that archive from embedded SQLite to a PostgreSQL Compose container;
live plan and conversation state remain session-only.
ADR 0019 defines GitHub Actions CI and gated app deployment through a local
Apple Silicon macOS launchd poller. Database migrations remain explicit.
ADR 0020 defines per-role output ceilings, process-local HTTP turn quotas and
redacted model-usage telemetry; actual monetary values remain in the runtime
environment and provider-project spend limits remain separately configured.
ADR 0021 makes Auth0 sign-in mandatory before React planner use and binds each
volatile planner session to its verified account owner.

