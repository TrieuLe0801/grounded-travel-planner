# Learning Log - 2026-10-14 Scope Reset

The active repository scope was reset from the older three-week POC to a
city/place sightseeing webapp.

## Decisions Recorded

- The current product is a session-only Streamlit travel-planning webapp.
- Runtime roles are limited to Coordinator and Planner for the first vertical
  slice.
- Planner is the only runtime role that may call Tavily search and propose plan
  mutations.
- Coordinator is user-facing and explains only validated committed results.
- The requested default model is exactly `gpt-5.5`.
- External model, search and trace providers stay behind typed interfaces.
- LangSmith traces are observability data and not application state.
- On 2026-10-16 the user selected Vietnamese as the default language for
  webapp chat requests and replies. Proper place names and source titles remain
  as provided by users and search results.
- The Vietnamese UI and fallback paths passed AppTest/pytest (40 total tests).
  A live Vietnamese add request inside the container committed revision 2 and
  produced a Vietnamese assistant reply with one search and no repair.
- On 2026-10-16 the user requested source-backed place images, a mapped route
  view, and a car moving to a clicked itinerary stop. ADR 0005 keeps these
  presentation features separate from the canonical plan and two-agent graph.
- The UI/UX Pro Max Codex skill was installed project-locally as version
  `2.15.0`. The visual itinerary passed 48 host/container tests and live
  Commons/Wikipedia metadata checks for two Hue landmarks. A fake-DOM
  JavaScript run confirmed click, reduced motion and interruption behavior;
  real-browser visual inspection remains open.
- Later on 2026-10-16 the user requested a separate page with an image of the
  compiled runtime graph, then explicitly requested removal of the itinerary
  route map shown in their screenshot. ADR 0006 supersedes the map/car portion
  of ADR 0005. Source-attributed place photos remain in the itinerary.
- The new graph page and photo-only itinerary passed focused offline tests.
  After the `get_graph_image()` integration, 47 tests passed in both host and
  Docker test runs. The rebuilt Compose
  container reached healthy status at `127.0.0.1:8503`. A previously commented
  source-place matching check was restored after the full suite exposed its
  failure; the remaining project lint and formatting checks then passed.
- The graph page now uses the PNG bytes returned by
  `TravelPlannerService.get_graph_image()` as requested. The existing local SVG
  renderer remains a fallback when Mermaid image rendering is unavailable.
- The user then requested temporary removal of `source_place_mismatch` because
  its token overlap caused repeated false rejections. URL provenance and the
  remaining deterministic source/hour checks stay enabled. Do not restore this
  issue code until a better relevance matcher is accepted.

## Evidence

- New charter and implementation plan describe the active product.
- ADR 0004 records the accepted two-agent runtime architecture.
- Phase 1A added the importable Coordinator/Planner runtime, typed provider
  boundaries and deterministic validators.
- Phase 1B added the session-only Streamlit form/chat adapter.
- Nineteen offline tests passed, including core routing/commit behavior and two
  Streamlit AppTests.
- The final live smoke committed a Hue plan with five Tavily-returned citations;
  all 14 matching LangSmith root/child runs carried the same `thread_id`.
- The Docker test target passed 19/19 tests on Linux/Python 3.10.22. The non-root
  Compose runtime reached health 200 and committed a live Hue plan from inside
  the container.
- On 2026-10-15 the user prioritized post-plan chat editing. The offline suite
  passed 39 tests, including eight versioned chat-edit cases and UI success/reject
  coverage. A live create-then-remove turn committed revision 2 on the same
  session and preserved the four untargeted stops.
- Added a separate, offline source-quality baseline with 16 manually labelled
  synthetic citations. The labels expose relevance and host-diversity metrics
  but do not measure live Tavily quality or change runtime commit rules.
- Migrated the original smoke to LangSmith v2 `runs.query()` and verified a
  live Hue run with 25 matching runs carrying the same `thread_id`.

## Open Risks

- Live providers still require local credentials and network access.
- Tavily results may not include opening hours; those hours must remain labeled
  unverified.
- Live source provenance is verified, but source editorial quality and domain
  diversity are not yet scored.

## Integration Learnings

- Tavily content must be bounded before Pydantic validation; one live snippet
  exceeded 1,000 characters.
- `ChatOpenAI.with_structured_output` needed `method="function_calling"` because
  strict response-format validation rejected Pydantic `HttpUrl`'s `uri` format.
- Search-call counters must advance at tool-attempt time, not only after a later
  model call succeeds.
- Edit validation must prove the requested add/remove/replace/reorder/day/time
  change was applied; generic schedule validity alone is not enough.
- Versioned uv derived-image tag names change with supported distro variants;
  copying a pinned uv binary into an official Python slim base was more robust.
- Container verification should cover both safe rejection and a successful live
  plan; provider reachability alone does not demonstrate commit behavior.
- Unverified hours are a permissible grounded data gap. Planner grounding must
  normalize them to `unverified`; only deterministic policy errors may block a
  commit, not advisory issues authored by the model.
- Reorder indices must match the chronological order visible in the UI;
  changing only the stored list order does not meet a user's reorder request.
- A repair must carry forward only trusted search/current-plan sources. Copying
  candidate references into that pool can launder a fabricated URL.
- Exact casefolded place-name comparison rejects benign Vietnamese accent and
  village-descriptor variants. Bound alias matching and ask Planner to retain
  the requested name; preserve old stops when validating an addition. The
  initial Lô Lô Chải live recheck hit OpenAI HTTP 429 `billing_not_active`.
  On 2026-10-16, a representative container flow added Lô Lô Chải, preserved
  the existing stop and committed revision 2 with one search and no repair.
- The Docker test stage must include versioned eval data and the smoke script
  imported by tests; excluding them from the build context caused collection
  errors even though host pytest passed.
