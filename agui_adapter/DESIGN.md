# Hermes AG-UI Adapter — Design & Decision Doc

> Exposes the Hermes agent over the **AG-UI protocol** (HTTP POST + SSE) so any
> [CopilotKit](https://github.com/CopilotKit/CopilotKit) / AG-UI front end can use
> Hermes as its agent backend — streaming text, tool calls, run lifecycle, and
> (v2) shared state, frontend actions, and human-in-the-loop.
>
> This doc is **executable**: §7 is a conformance checklist the build is tested against.

---

## 1. One-paragraph summary

CopilotKit is a *frontend stack* — it drops an AI copilot UI (chat, generative UI,
"are-you-sure?" prompts) into a web app. It talks to agents through the open
**AG-UI protocol**. Hermes *is* an agent (Python). The AG-UI adapter is the bridge:
a small HTTP server that accepts an AG-UI `RunAgentInput`, runs one Hermes turn, and
re-broadcasts Hermes' live output (typing, tool use, thinking, completion) as the
AG-UI event stream the front end understands. Result: **Hermes becomes a drop-in
brain for any AG-UI/CopilotKit web product.**

---

## 2. Q&A

**Q: What problem does this solve?**
A: Today you can chat with Hermes in a terminal, an IDE (ACP), or a messaging app
(Telegram/Slack), or use its own dashboard. There is no way to embed Hermes as the
agent inside *your own custom web product* with *your* UI, branding, state, and
interactive components. AG-UI is the standard seam for exactly that. This adapter
fills the "Hermes powers my web app's copilot" gap.

**Q: Who is the consumer?**
A: A **web/product developer** building a user-facing app with CopilotKit (or any
AG-UI client — LangGraph/CrewAI/AG-UI-native UIs). Not an end-user directly; the
end-user sees only the developer's app.

**Q: What's the transport / contract?**
A: A single HTTP `POST` endpoint that accepts `RunAgentInput` (thread_id, run_id,
messages, tools, state, context) and returns a **Server-Sent Events** stream of
AG-UI events (`RUN_STARTED`, `TEXT_MESSAGE_*`, `TOOL_CALL_*`, `TOOL_CALL_RESULT`,
`RUN_FINISHED`, `RUN_ERROR`). Encoding handled by the official `ag-ui-protocol`
Python SDK's `EventEncoder`, so the wire format is canonical, not guessed.

### Common use cases (the 80%)
1. **Sidebar copilot in a SaaS app** — "ask Hermes" assistant docked in your product.
2. **Customer-facing assistant** on a marketing/site with your own branding and theme.
3. **Internal tools / ops dashboards** where Hermes is the brain but you own the UI.
4. **Frontend-defined actions** — the web app exposes `useCopilotAction` tools
   (navigate, fill a form, update a cart, highlight a row) that Hermes can call.
5. **Generative UI** (v2) — Hermes' decisions render rich components (charts, cards,
   forms) instead of plain text.
6. **Human-in-the-loop** (v2) — Hermes proposes an action; the user approves/edits in
   a custom UI before it proceeds.
7. **Framework swap-in** — a front end already speaking AG-UI (built for LangGraph/
   CrewAI) can point at Hermes with a one-line URL change.

### Edge use cases (the long tail)
- **Voice / multimodal UIs** driven off the AG-UI event stream.
- **React Native / mobile** copilots via CopilotKit mobile.
- **Multi-agent boards** — an AG-UI app orchestrating Hermes *and* other AG-UI agents.
- **Observability/replay** — capture the AG-UI event stream as a structured trace of
  an agent run for debugging or audit.
- **Headless conformance harness** — a non-UI client that drives runs purely to test
  Hermes behavior through a stable protocol.

### When to use it
- You are building a **web/product UI** and want Hermes as the embedded agent.
- You want **streaming** + **tool-call visibility** + (later) **generative UI / shared
  state / HITL** in a browser.
- You want **ecosystem interop** (CopilotKit, AG-UI, LangGraph/CrewAI front ends).

### When NOT to use it (and what to use instead)
| You want… | Use this instead |
|---|---|
| Hermes inside your **code editor** (Zed/VS Code/JetBrains) | **ACP adapter** (`hermes acp`) |
| Another **AI agent to call Hermes' tools / conversation data** | **MCP server** (`hermes mcp serve`) |
| Chat with Hermes in **Telegram/Slack/Discord/WhatsApp/Signal** | **Gateway platforms** |
| A **local control panel** for your own Hermes | **Built-in dashboard** |
| **Terminal / scripting** | the `hermes` CLI / `-z` one-shot |
| **Backend→backend**, no UI, a single function call | **MCP tool**, not a full agent run |
| A **stateless RPC** to one capability | **MCP tool** (granular), not AG-UI (whole-agent) |

---

## 3. How Hermes distinguishes this from its neighbors

All five "expose Hermes outward" surfaces, on the axes that actually differ:

| Surface | Consumer | Transport | Granularity | Killer feature |
|---|---|---|---|---|
| **AG-UI adapter** (this) | Custom **web app** devs (CopilotKit) | HTTP POST + **SSE** | Whole agent loop | **Generative UI, shared state, frontend actions, HITL in a browser** |
| **ACP adapter** | **Code editors** (Zed/VSCode/JetBrains) | JSON-RPC over **stdio** | Whole agent loop | Editor-native coding agent + file/permission integration |
| **MCP serve** | **Other AI agents** / Claude Desktop | MCP **stdio/HTTP** | **Tools** (~10: conversations, messages, events, permissions) | Let another agent *borrow Hermes' tools & state* |
| **Gateway platforms** | **Chat users** on messaging apps | Each platform's API | Whole agent loop | Reach users where they already chat |
| **Dashboard / web** | The **owner**, via browser | HTTP/WebSocket to its *own* React app | Whole agent loop | Hermes' built-in control panel |

**The one-line distinction:**
- **ACP** = "use Hermes *in my editor*."
- **MCP** = "let my *other agent* call Hermes' tools."
- **Gateway** = "chat with Hermes *in a messaging app*."
- **Dashboard** = "Hermes' *own* UI."
- **AG-UI (this)** = "make Hermes the brain *inside the web product I'm building*."

**Decision tree:**
```
Are you building a custom web UI where an agent should live?
├─ yes → does that UI use CopilotKit / speak AG-UI? ───────────────▶ AG-UI ADAPTER ✅
│         └─ no, it's an IDE/editor ─────────────────────────────▶ ACP
└─ no →
   ├─ you want another AI agent to call Hermes' tools ───────────▶ MCP serve
   ├─ you want to chat via Telegram/Slack/etc ──────────────────▶ Gateway
   └─ you just want a local control panel ──────────────────────▶ Dashboard
```

**Why not just reuse ACP or MCP for web?**
- ACP is JSON-RPC/stdio and editor-shaped (file system, permission prompts, slash
  commands) — wrong transport and wrong surface for a browser product.
- MCP exposes *tools*, not a streaming conversation with generative UI / shared state.
  A CopilotKit app on MCP gets Hermes' functions, **not** Hermes-as-copilot.
- AG-UI is the protocol the web/agent-UI ecosystem actually standardized on
  (CopilotKit, LangGraph, CrewAI, AWS, Microsoft). Speaking it natively is the point.

---

## 4. Capability scope

**v1 (this build) — get a real streaming chat working:**
- ✅ Accept `RunAgentInput`; run one Hermes turn per request.
- ✅ Stream assistant text token-by-token (`TEXT_MESSAGE_START/CONTENT/END`).
- ✅ Surface tool calls (`TOOL_CALL_START/ARGS/END`) and results (`TOOL_CALL_RESULT`).
- ✅ Run lifecycle (`RUN_STARTED`, `RUN_FINISHED`, `RUN_ERROR`).
- ✅ Map AG-UI `thread_id` → a persistent Hermes session (conversation continuity).
- ✅ `hermes agui` command (port 9100); configurable host/port; CORS for browser clients.
- ✅ Reuse Hermes' configured model/provider (free Codex etc.) — no separate config.

**v2 (deferred, documented so it's not forgotten):**
- ⏳ Shared state sync (`STATE_SNAPSHOT` / `STATE_DELTA`).
- ⏳ Frontend-defined tools/actions executed in the browser (round-trip).
- ⏳ Human-in-the-loop approval UI (map Hermes' approval callback → AG-UI interrupt).
- ⏳ Reasoning/thinking events (`THINKING_*` / reasoning channel).
- ⏳ Multi-tenant auth / API keys on the endpoint.

---

## 5. Architecture (summary)

```
CopilotKit React app  ──POST RunAgentInput──▶  agui_adapter (FastAPI)
        ▲                                            │  build/lookup session by thread_id
        │  ◀──SSE: AG-UI events──                    │  set Hermes callbacks
        │                                            ▼
        └──────────────────────────────  Hermes AIAgent.run_conversation()  (worker thread)
                                          callbacks fire ──▶ asyncio.Queue ──▶ SSE streamer
```
- Hermes' agent runs **sync in a thread**; the server is **async**. A per-run
  `asyncio.Queue` bridges them (callbacks `put`, streamer `get`+`encode`). This is the
  same proven pattern as `acp_adapter`.

---

## 6. Edge cases & failure modes the build must handle

1. **Agent raises mid-run** → emit `RUN_ERROR`, never hang the SSE stream.
2. **Empty / whitespace user message** → 400 or a clean no-op run, not a crash.
3. **Concurrent runs on different threads** → isolated sessions, no cross-talk.
4. **Concurrent runs on the *same* thread** → serialized or rejected, no interleaved
   history corruption.
5. **Client disconnects mid-stream** → stop work, free the session lock, no zombie.
6. **Very large tool output** → respect Hermes' tool-output caps; don't blow the stream.
7. **Tool call with no result** (e.g. blocked/approval-denied) → still close the
   `TOOL_CALL_*` group cleanly.
8. **Provider 429 / upstream error** (the Codex/Anthropic saga) → surfaces as
   `RUN_ERROR` with a readable message, not a silent dead stream.
9. **`thread_id` reused after restart** → rehydrate history from Hermes' session store.
10. **Browser CORS preflight** → `OPTIONS` handled; configurable allowed origins.

---

## 7. Conformance checklist (tested AFTER build)

Each item is a falsifiable assertion. After building I run these and report pass/fail.

| # | Assertion | How verified |
|---|---|---|
| C1 | `from agui_adapter.server import build_app` imports without error | import in venv |
| C2 | `ag-ui-protocol` is an installed, importable dependency (`ag_ui.core`, `ag_ui.encoder`) | import |
| C3 | `POST /` with a valid `RunAgentInput` returns `200` + `text/event-stream` | live curl |
| C4 | The stream begins with `RUN_STARTED` and ends with `RUN_FINISHED` | parse SSE |
| C5 | A plain "say hi" prompt yields ≥1 `TEXT_MESSAGE_CONTENT` with non-empty delta | parse SSE |
| C6 | A prompt that uses a tool yields `TOOL_CALL_START`→`TOOL_CALL_END` (+ result) | parse SSE |
| C7 | An induced agent error yields `RUN_ERROR`, stream closes cleanly | fault inject |
| C8 | Same `thread_id` across two requests preserves conversation memory | 2-call test |
| C9 | `hermes agui --help` works and documents host/port | CLI |
| C10 | CORS preflight `OPTIONS /` returns permissive headers for browser use | curl -X OPTIONS |
| C11 | Empty message is handled gracefully (no 500/stacktrace) | curl |
| C12 | README documents: install extra, run command, CopilotKit wiring snippet | inspect |
| C13 | Adapter reuses Hermes' configured model/provider (no 2nd config) | code review + run |
| C14 | This DESIGN doc's "when NOT to use" table matches the actual neighbor commands | cross-check CLI |

**Result:** _(filled in after build — see §8)_

---

## 8. Conformance results

Tested 2026-06-05. Protocol checks via `agui_adapter/test_conformance.py` (an
injected fake agent — no LLM/quota), plus a **live end-to-end run** against the
real Hermes agent. **14/14 PASS.**

| # | Result | Evidence |
|---|---|---|
| C1 | ✅ | `import build_app` OK |
| C2 | ✅ | `ag_ui.core` / `ag_ui.encoder` import OK |
| C3 | ✅ | `POST /` → `200` + `text/event-stream` (fake + live) |
| C4 | ✅ | stream = `RUN_STARTED … RUN_FINISHED` (fake + live) |
| C5 | ✅ | live: 3× `TEXT_MESSAGE_CONTENT` deltas assembled to `"agui works"` |
| C6 | ✅ | fake: `TOOL_CALL_START/ARGS/END` + `TOOL_CALL_RESULT` emitted |
| C7 | ✅ | injected agent error → `RUN_ERROR`, no `RUN_FINISHED` |
| C8 | ✅ | same `thread_id`: 2nd run sees grown history (`[0, 2]`) |
| C9 | ✅ | `hermes agui --help` documents host/port (installed `hermes` needs code sync) |
| C10 | ✅ | `OPTIONS /` returns `access-control-allow-origin` |
| C11 | ✅ | whitespace message → clean `RUN_STARTED/RUN_FINISHED`, no 500 |
| C12 | ✅ | README: install extra, run cmd, curl, CopilotKit route+UI snippets |
| C13 | ✅ | `session.py` uses `load_config()`+`resolve_runtime_provider()`; live run used configured model |
| C14 | ✅ | `hermes acp`, `hermes mcp`, `hermes mcp serve` all exist |

Live SSE sample (real agent):
```
data: {"type":"RUN_STARTED","threadId":"smoke1","runId":"r1"}
data: {"type":"TEXT_MESSAGE_START","messageId":"…","role":"assistant"}
data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"…","delta":"ag"}
data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"…","delta":"ui"}
data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"…","delta":" works"}
data: {"type":"TEXT_MESSAGE_END","messageId":"…"}
data: {"type":"RUN_FINISHED","threadId":"smoke1","runId":"r1"}
```

**Not yet exercised live:** real tool-call run (proven deterministically via C6),
multi-client concurrency at scale, and the v2 features (state/HITL/reasoning).
</content>
