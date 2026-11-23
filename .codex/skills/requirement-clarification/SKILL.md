---
name: requirement-clarification
description: Clarify product tradeoffs and missing acceptance decisions during research and planning, or run a user-requested deep requirements interview.
---

# Requirement Clarification

Use for Codex development requirements, not the travel-planner runtime chat.
Researcher gathers evidence; Planner resolves remaining design branches. The
primary session asks the user and records answers. Other agents report missing
decisions to the primary session rather than independently interviewing the user.

For research or proposal requests, complete this decision check before presenting
a recommended solution. A technical approach does not settle product choices
such as speed versus source quality, initial result detail, or minimum coverage.
Researcher reports those choices after checking existing decisions; Planner
checks again before finalizing its plan. The primary session asks at the
handoff and returns answers to both roles as needed. Do not present a dependent
recommendation as final while an answer is pending.

## Choose the mode

- **Focused:** Default when a missing decision changes scope, acceptance,
  irreversible effects, or a project contract. Ask only the smallest set of
  blocking questions. Continue independent research and implementation while
  waiting; use a stated reasonable assumption for optional preferences.
- **Deep interview:** Use when the user explicitly asks to be grilled or to
  explore every design branch. Map decisions and their prerequisites. Ask each
  currently answerable branch in a round, then wait for answers before opening
  dependent branches. End when every material branch has an answer or a stated
  exclusion. Do not make a final dependent decision for the user.

## Before asking

1. Read the request, current Goal Card, active charter, accepted ADRs, relevant
   code, and prior explicit user decisions. Investigate facts available through
   repository tools or authoritative sources. Do not ask the user to look up
   facts the agent can verify.
2. Separate a user decision from an implementation choice the project already
   delegates to an agent. Ask only about the former. Do not re-ask answered
   questions or seek permission for authorized reversible work.
3. Order questions by dependency. Give each question concise context, two or
   three concrete choices when useful, and a recommended choice with its tradeoff.
   Keep independent questions in one round; hold dependent questions for the
   next round. Match the user's language.
4. Record each answer, remaining unknown, and any assumption in the Goal Card.
   Record an explicit new project decision in the current durable records before
   relying on it in later sessions. Resume dependent work only after required
   answers arrive.

Do not turn a routine task into an interview. Do not demand a final confirmation
when acceptance and authority are already clear. If the user asks only for a
specification or interview, stop after delivering that artifact; otherwise
continue the authorized work once blocking decisions are settled.
