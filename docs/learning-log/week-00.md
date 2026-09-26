# Learning Log — Week 00

Last updated: 2026-09-26
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
| Greenfield baseline recorded | `docs/experiments/baseline-environment.md` | Partial: Docker Engine pending |
| Codex project context created | `AGENTS.md` | Done |
| Week 0 status made durable | `PROJECT_STATUS.md` | Done |
| Roadmap state exported | `docs/progress/roadmap-progress.json` | Done |
| Machine-readable golden set | `data/eval/travel-scenarios-v0.jsonl` | Not started |
| Travel-planner tests and metrics | — | N/A: no application implementation yet |
| Development-hook tests | `tests/test_format_python_hook.py` | Done: 2 passed |

## Decisions

- Use a clarify-then-generate interaction for the MVP.
- Start with a deterministic single-agent workflow.
- Use deterministic synthetic flight and lodging fixtures.
- Keep live provider integrations, durable feedback and severe-allergy support
  outside the MVP.
- Keep long-term memory outside the MVP until experiments demonstrate value.
- Keep all durable decisions in the repository, not only in chat or browser
  storage.
- Use Python `>=3.10`, `uv`, `pytest`, isort, Black, flake8, Ruff and Docker
  Desktop as the development baseline for the MacBook M1.

## Open questions

- Which Docker Engine version is installed when the daemon is available?
- Which checkpointer will be used after the in-memory learning spike?
- What typed fields are minimally sufficient for accessibility and dietary
  constraints?
- Which exact metrics will compare a LangChain loop with explicit LangGraph
  orchestration?
- What minimum improvement would justify a multi-agent topology?

## Next learning session

1. Capture the Docker Engine version when its daemon is available.
2. Define metric formulas without measured values.
3. Create the JSONL schema and first five happy-path evaluation cases.

### 2026-09-26 — Coding/testing agents and Python formatting hook

**Question**

How can Codex support coding and testing work while automatically formatting
Python edits without changing the travel planner's runtime agent topology?

**Learned**

- Project-scoped Codex agents are TOML files under `.codex/agents/`.
- A project `PostToolUse` hook can inspect an `apply_patch` event and run local
  commands. Codex requires trust review for new or changed non-managed hooks.
- Flake8 checks style but does not reformat; isort and Black make the edits.

**Tried**

- Added `coding` and `testing` agents and a hook limited to edited Python files
  inside the repository.
- Locked development dependencies with `uv`, using Python 3.10.21 on the Mac.
- Tested path filtering and tool order with pytest, then ran a live hook smoke
  test with `/usr/bin/python3` and a temporary Python file.
- Ran the full tooling suite. The initial flake8 run scanned `.venv`, and Ruff
  objected to the hook's Python 3.9-compatible type hint; configuration was
  corrected before the final checks.

**Result**

- `uv run pytest`: 2 passed.
- `uv run isort --check-only . .codex/hooks/format_python.py`: passed.
- `uv run black --check . .codex/hooks/format_python.py`: passed.
- `uv run flake8 . .codex/hooks/format_python.py`: passed.
- `uv run ruff check . .codex/hooks/format_python.py`: passed.
- Hook smoke test: passed; isort sorted imports, Black formatted code, and
  flake8 returned no warning.
- Travel-planner application tests and metrics remain `N/A`.

**Decision**

Use isort and Black for formatting, flake8 for style checks, and Ruff for
supplementary linting. Keep coding/testing agents separate from the travel
planner's single-agent-first architecture.

**Evidence**

- `.codex/agents/`, `.codex/hooks.json`, `.codex/hooks/format_python.py`
- `tests/test_format_python_hook.py`, `pyproject.toml`, `uv.lock`
- `docs/adr/0001-python-development-tooling.md`

**Next**

- Review and trust the hook through `/hooks` in a new Codex session, then
  continue the pending Week 0 specification tasks.

### 2026-09-26 — Development manager and specialist model assignments

**Question**

How should a Codex manager receive development requests and delegate planning,
coding and testing while preserving the product's single-agent-first decision?

**Learned**

- Project `.codex/config.toml` can set the primary Codex model; custom agent TOML
  files can pin their own models and reasoning effort.
- GPT-6 Sol, GPT-5.6 Terra and GPT-5.5 are documented model identifiers.
  Sources: <https://learn.chatgpt.com/docs/agent-configuration/subagents>,
  <https://developers.openai.com/api/docs/models/gpt-6-sol>,
  <https://developers.openai.com/api/docs/models/gpt-5.6-terra>,
  <https://developers.openai.com/api/docs/models/gpt-5.5>.

**Tried**

- Set the primary session to `gpt-6-sol` and added `manager`, `planner`,
  `coding` and `testing` agent definitions with explicit models.
- Defined bounded handoffs and shared-file coordination in the manager role.
- Parsed all TOML files and asserted the four model assignments.

**Result**

- Agent configuration assertion: 4 roles and model assignments verified.
- `uv run pytest`: 2 passed.
- isort, Black, flake8, Ruff, `uv lock --check` and `git diff --check`: passed.
- Runtime delegation awaits a new trusted Codex project session; no live
  model call or subagent run was claimed.

**Decision**

Use `gpt-6-sol` for the primary manager and explicit manager role,
`gpt-5.6-terra` for development planning, and `gpt-5.5` for coding and testing.
These roles coordinate software work and do not change the travel planner's
runtime architecture.

**Evidence**

- `.codex/config.toml` and `.codex/agents/*.toml`
- `AGENTS.md`, `README.md`, `docs/adr/0001-python-development-tooling.md`

**Next**

- Start a trusted Codex project session to use the assigned roles on the next
  development task.

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
