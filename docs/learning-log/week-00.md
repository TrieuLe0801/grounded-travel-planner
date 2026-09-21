# Learning Log — Week 00

Last updated: 2026-09-21  
Status: In progress

## Week objective

Define the product boundary, constraints, evaluation direction and durable
project context before implementing LangGraph.

## Learned

### Orchestration

- An agent is not necessarily one node. A LangGraph node is a unit of work and
  may contain deterministic code, a model call, a tool call or an entire agent.
- Explicit state and conditional routing are useful when clarification, partial
  research, bounded repair and user decisions must be observable and testable.
- LangGraph is expected to improve workflow reliability and inspectability, not
  the underlying model's intelligence.

### Multi-agent

- Multi-agent is a hypothesis to test, not the MVP starting point.
- A fair comparison must hold the model, tools, fixtures, constraints and eval
  cases constant.
- Specialist agents are valuable only if quality gains justify extra calls,
  tokens, latency and orchestration complexity.

### Memory

- Short-term thread state is required for clarification and trip constraints.
- Long-term memory is not required for the MVP.
- Sensitive preferences require explicit consent before durable storage, and a
  current request must override stored preferences.

### Product grounding

- A hard budget covers the whole trip, including flights and accommodation.
- Unknown accessibility or dietary evidence is not confirmation.
- Synthetic prices must be deterministic, labeled and linked to fixture IDs,
  never presented as live prices.

## Tried

- Drafted and reviewed the product charter through multiple decision rounds.
- Separated required, optional and conditional inputs.
- Defined five workflow outcomes for clarification, incomplete research,
  user decisions, unavailable plans and ready plans.
- Described 22 initial acceptance scenarios in the charter.
- Recorded the greenfield baseline and target control flow.
- Created durable Codex instructions, project status and exported roadmap state.

## Result and evidence

| Result | Evidence | Status |
|---|---|---|
| MVP charter accepted | `docs/project-charter.md` | Done |
| Greenfield baseline recorded | `docs/experiments/baseline-environment.md` | Partial: Mac details pending |
| Codex project context created | `AGENTS.md` | Done |
| Week 0 status made durable | `PROJECT_STATUS.md` | Done |
| Roadmap state exported | `docs/progress/roadmap-progress.json` | Done |
| Machine-readable golden set | `data/eval/travel-scenarios-v0.jsonl` | Not started |
| Executable tests and metrics | — | N/A: no implementation yet |

## Decisions

- Use a clarify-then-generate interaction for the MVP.
- Start with a deterministic single-agent workflow.
- Use deterministic synthetic flight and lodging fixtures.
- Keep live provider integrations, durable feedback and severe-allergy support
  outside the MVP.
- Keep long-term memory outside the MVP until experiments demonstrate value.
- Keep all durable decisions in the repository, not only in chat or browser
  storage.
- Use Python `>=3.10`, `uv`, `pytest`, Ruff and Docker Desktop as the development
  baseline for the MacBook M1.

## Open questions

- Which exact Python minor version satisfying `>=3.10` is installed on the
  MacBook M1?
- Which exact macOS, `uv`, Git, Docker Engine and Compose versions are installed?
- Which checkpointer will be used after the in-memory learning spike?
- What typed fields are minimally sufficient for accessibility and dietary
  constraints?
- Which exact metrics will compare a LangChain loop with explicit LangGraph
  orchestration?
- What minimum improvement would justify a multi-agent topology?

## Next learning session

1. Capture the exact MacBook M1 environment versions.
2. Define metric formulas without measured values.
3. Create the JSONL schema and first five happy-path evaluation cases.

## Entry template

Append future entries using this structure:

```markdown
### YYYY-MM-DD — Topic

**Question**

What am I trying to understand or prove?

**Learned**

- Concept in my own words.
- Source or documentation link.

**Tried**

- Experiment, command, input or code path.

**Result**

- Observed output, trace, metric or failure.

**Decision**

- Keep, change, defer or reject, with reason.

**Evidence**

- Repository file, test name, LangSmith experiment or trace reference.

**Next**

- One concrete follow-up action.
```
