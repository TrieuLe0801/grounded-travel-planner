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
- Format app-rendered dates using the selected UI locale. Keep date-only values
  in ISO form. Use a React date picker with localized month and weekday labels;
  set the Streamlit date input format from the same preference.
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
- Itinerary and saved-tour dates change format with the selected UI locale;
  stored date values and provider source data remain unchanged.
- The locale has no effect on routing, source provenance, validation, search
  bounds or plan commit semantics.

## Review Triggers

- The user requests another UI or assistant language.
- The app adopts durable user accounts or cross-session preferences.
- The app adds locale-dependent formatting for numbers or source metadata.

## User Amendment — 2026-11-08 — React Date Picker Locale

The native browser date control continued to show browser-language month and
weekday labels after the app switched to English. Replace that React control
with an in-app calendar whose month, weekday and action labels use the selected
session locale. Keep the selected date in ISO form for session and API data.
