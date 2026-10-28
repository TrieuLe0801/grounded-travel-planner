# Focused agent security evaluation

Use only the rows relevant to the assigned change. Cloudflare's [AI and LLM audit guidance](https://github.com/cloudflare/security-audit-skill/blob/main/skills/security-audit/AI-AND-LLM.md) informed these checks; this repository's `AGENTS.md` and accepted ADRs define the actual product contract.

| Boundary | Deterministic fixture or inspection | Required observation |
| --- | --- | --- |
| Search result or user text → model instruction | Put instruction-like text in a mocked lower-trust search result or user field; trace prompt assembly and the committed response. | The text remains data; it cannot replace system policy, forge a provider citation, or directly authorize a plan change. |
| Model output → plan commit | Return a malformed, ungrounded, or policy-invalid candidate from a mocked model. | Code validation rejects it, preserves the previous canonical plan, and explains the failed request without laundering candidate sources. |
| Session or summary → another session | Use two distinct dummy sessions with different plans, histories, locale choices, and pending turns. | No cross-session read/write, cache reuse, or pending-result integration; context and summary stay within configured bounds. |
| Model/tool request → Tavily | Mock search decisions, failed calls, retries, and Planner/Chat turns against the shared tool node. | Only that node calls the provider, the common per-turn limit counts attempts, and tool results return to the requesting role. |
| Provider fallback → graph state | Make the primary model fail and the fallback succeed or fail with mocked adapters. | Same prompt/schema and bounded graph budget; no duplicate search or plan mutation from a failed attempt; safe localized failure if both fail. |
| Agent output → UI, logs, traces | Supply model text with HTML/URL markers and dummy secrets; inspect rendering and trace payloads. | Renderer handles untrusted output safely; secrets, raw queries, credentials, and other users' context are absent from traces and logs. |

For a suspected security finding, write down: lower-trust actor/input; affected principal or shared resource; execution identity and capability; intended deterministic control; source path from input to decision/sink; observed result; and the smallest effective fix or exact validation blocker. A guardrail prompt or structured-output schema alone does not prove authorization. Conversely, an attacker-controlled sentence with no reachable privileged action, disclosure, or state change is not a confirmed vulnerability.

Use a minimal local effect with dummy principals and data. Avoid availability or spend tests on shared services. If a result depends on deployment, browser, provider, or identity behavior absent from the repository and fixture, mark `needs_validation` with a safe owner-observed check. For a consequential finding, ask a fresh reviewer to inspect the source and attempt to disprove it without handing them the proposed conclusion; record any correction before reporting it.
