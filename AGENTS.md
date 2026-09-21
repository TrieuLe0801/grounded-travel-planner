# Grounded Travel Planner — Codex Instructions

## Project boundary

- This repository is an independent LangChain, LangGraph and LangSmith learning
  project.
- Use only decisions and artifacts recorded in this repository as project
  context unless the user explicitly supplies another source.
- The MVP is a grounded travel-planning proof of concept, not a booking system.

## Read before making changes

Before editing code or project decisions, read these files in order:

1. `PROJECT_STATUS.md`
2. `docs/project-charter.md`
3. the current file under `docs/learning-log/`
4. relevant records under `docs/adr/`, when they exist
5. `docs/experiments/baseline-environment.md` for environment-dependent work

Treat repository Markdown as the durable source of truth. Browser
`localStorage`, chat history and assumptions are not project evidence unless
they have been written to the repository.

## Architecture principles

- Use LangGraph for explicit state, routing, interrupts, bounded loops and
  persistence.
- Use LangChain for model, tool and structured-output integrations.
- Use LangSmith for traces, datasets and evaluations after an executable flow
  exists.
- Start with a deterministic single-agent workflow. Add specialist agents only
  after a controlled comparison demonstrates value.
- Keep short-term trip state separate from long-term user memory. Long-term
  memory is post-MVP unless an ADR changes that decision.
- External providers must be behind typed, provider-independent interfaces.

## Product invariants

- Never fabricate sources, prices, availability or tool results.
- Label fixture-based flight and lodging estimates as `synthetic_estimate` and
  include their fixture ID; do not attach a fake URL.
- A supplied total-trip budget is a hard limit and includes flight, lodging,
  food, local transport and activities.
- `UNKNOWN` evidence never satisfies an accessibility or dietary hard
  constraint.
- Current-request constraints override stored preferences.
- Severe-allergy recommendations and safety guarantees are outside the MVP.
- Preserve the workflow outcomes defined in `docs/project-charter.md`.

## Working agreements

- Prefer small, typed, testable Python modules and deterministic fixtures.
- Keep network and model calls out of unit tests.
- Bound all agent and repair loops explicitly.
- Store secrets only in ignored environment files; never commit credentials or
  raw sensitive preferences.
- Do not claim tests, metrics or providers exist until the corresponding
  executable artifact exists.
- Do not select Python, package-manager or container versions on the user's
  behalf while the baseline still marks those decisions as pending.
- Update `PROJECT_STATUS.md`, the current learning log and
  `docs/progress/roadmap-progress.json` when a checklist item is completed.
- Add or update an ADR when changing a confirmed architectural decision.
- Run the narrowest relevant checks after a change, then the full available
  suite. If no executable checks exist, report that status as `N/A`.

## Completion evidence

A task is complete only when its durable artifact exists and its verification
result is recorded. A checked box in `docs/roadmap.html` alone is not evidence.
