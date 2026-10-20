# ADR 0013 - Bilingual Session Language

Status: Accepted
Date: 2026-10-20

## Context

The webapp and runtime agents previously presented Vietnamese only. The user
requested an English version and a way to switch the webapp between Vietnamese
and English while preserving the active itinerary and chat session.

## Decision

- Support `vi` and `en`; Vietnamese remains the default.
- Store the selected locale in the existing in-memory session. The React UI
  reads and updates it through the session API. Streamlit stores the same
  preference in its current `Session State`.
- Changing the locale updates interface labels and the language for future
  model-authored turns. It does not reset the plan, conversation, rolling
  summary, current view or pending background turn. Starting a new trip keeps
  the selected locale.
- Capture the locale when a turn is submitted. A pending turn keeps that locale
  through the background runner and LangGraph; a later language switch applies
  to subsequent turns.
- Coordinator summaries, new Planner itinerary prose, Chat responses and
  code-owned fallbacks follow the captured locale. User-entered text, place
  names, existing conversation and plan text, provider source titles/snippets/
  URLs, and factual evidence remain unchanged.
- Keep intent codes, schedule/source validation and commit policy
  language-independent. Present known validation issues in the selected locale
  by stable issue code; preserve raw issue evidence for unknown codes.
- Keep the preference session-only. Do not add browser local storage, database
  persistence or cross-session language tracking.

## Alternatives Considered

- Store the locale in browser local storage: rejected because application state
  is session-only and the current session API already owns UI preferences.
- Translate the stored plan and transcript when the selector changes: rejected
  because it could rewrite user text, place names, citation titles or evidence.
- Let a locale change affect an in-flight worker: rejected because each
  background result must remain deterministic for its captured request.

## Consequences

- A language change is immediately visible in both React and Streamlit while
  the plan and pending turn remain owned by the same session.
- Existing conversation and generated plan prose can remain in their original
  language after switching. New model-authored content uses the selected
  locale.
- The locale has no effect on routing, source provenance, validation, search
  bounds or plan commit semantics.

## Review Triggers

- The user requests another UI or assistant language.
- The app adopts durable user accounts or cross-session preferences.
- Locale-dependent formatting of dates, numbers or source metadata becomes a
  product requirement.
