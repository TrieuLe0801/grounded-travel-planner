# Grounded Travel Planner

A personal learning project and proof of concept for building a grounded travel
planning agent with LangChain, LangGraph and LangSmith.

The project is currently in **Week 0: specification and baseline**. Application
implementation intentionally has not started yet.

## Current progress

- Week 0: **22 / 34 items complete (65%)**
- Project charter: accepted for MVP
- Code, tests and measured runtime metrics: `N/A` until implementation begins

See `PROJECT_STATUS.md` for the current Done / Now / Next / Blockers view.

## Repository map

```text
.
├── AGENTS.md                              # Durable instructions for Codex
├── PROJECT_STATUS.md                      # Current state and next actions
├── README.md
├── data/eval/                             # Machine-readable eval cases (pending)
├── docs/
│   ├── adr/                               # Architecture decisions
│   ├── experiments/baseline-environment.md
│   ├── learning-log/week-00.md
│   ├── progress/roadmap-progress.json
│   ├── project-charter.md
│   └── roadmap.html                       # Interactive learning roadmap
├── src/                                   # Application code (not started)
└── tests/                                 # Tests (not started)
```

## Continue on a MacBook M1

After pushing this folder to a Git host, clone it on the Mac and open Codex from
the repository root:

```bash
git clone <repository-url>
cd grounded-travel-planner
```

Before installing project dependencies, record the actual machine baseline:

```bash
sw_vers
uname -m
python3 --version
git --version
docker --version
docker compose version
```

Copy the results into `docs/experiments/baseline-environment.md`. Values that
are not installed should remain explicit `TODO` items; do not invent them.

Codex automatically reads repository-level `AGENTS.md` when a new session is
started from this repository. A useful first prompt is:

```text
Read AGENTS.md, PROJECT_STATUS.md, docs/project-charter.md and
docs/learning-log/week-00.md. Summarize the current Week 0 status and implement
only the first incomplete next action.
```

## Roadmap state

`docs/roadmap.html` is a convenient interactive view. Its browser state is not
the source of truth. Exported progress belongs in
`docs/progress/roadmap-progress.json`, and completed work must be supported by a
repository artifact.

## Git setup

This folder is initialized as a local Git repository but contains no commit and
no remote. Review the files, then add your remote and create the first commit
when ready.

