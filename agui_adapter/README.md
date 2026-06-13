# Hermes AG-UI Adapter

Expose the Hermes Agent as an **AG-UI** agent so any **CopilotKit** frontend (or
other [AG-UI](https://ag-ui.com) client) can drive Hermes — streaming its text,
tool calls, and tool results into a generative chat UI.

AG-UI is the open agent↔UI streaming protocol CopilotKit is built on. This
adapter is the server side of that protocol; it mirrors [`acp_adapter/`](../acp_adapter)
(which exposes Hermes over the Agent Client Protocol for editors) and reuses the
same `AIAgent` streaming callbacks.

```
CopilotKit React app ──HTTP/SSE──▶ CopilotRuntime ──AG-UI──▶ hermes agui ──▶ AIAgent
        (chat UI)                    (Next.js route)          (this adapter)   (Hermes)
```

## Install & run

```bash
pip install -e '.[agui]'      # fastapi, uvicorn, ag-ui-protocol
hermes agui --port 9100       # serves the AG-UI endpoint at POST http://127.0.0.1:9100/
```

Env overrides: `HERMES_AGUI_HOST`, `HERMES_AGUI_PORT`, `HERMES_AGUI_LOG_LEVEL`.
The agent model/provider come from your normal `~/.hermes/config.yaml` — whatever
Hermes is configured to use, the AG-UI agent uses.

Smoke-test it without a frontend:

```bash
curl http://127.0.0.1:9100/health
# {"status":"ok","agent":"hermes","protocol":"ag-ui"}

curl -N -X POST http://127.0.0.1:9100/ \
  -H 'content-type: application/json' \
  -d '{"threadId":"t1","runId":"r1","messages":[{"id":"m1","role":"user","content":"say hi in 3 words"}],"tools":[],"context":[],"state":{}}'
# → SSE stream: RUN_STARTED, TEXT_MESSAGE_START/CONTENT/END, RUN_FINISHED
```

## Wire it into a CopilotKit app

**1. Runtime route** — `app/api/copilotkit/route.ts` (Next.js App Router):

```ts
import {
  CopilotRuntime,
  copilotRuntimeNextJSAppRouterEndpoint,
  ExperimentalEmptyAdapter,
} from "@copilotkit/runtime";
import { HttpAgent } from "@ag-ui/client";

const runtime = new CopilotRuntime({
  agents: {
    // points at `hermes agui`
    hermes: new HttpAgent({ url: process.env.HERMES_AGUI_URL ?? "http://localhost:9100/" }),
  },
});

export const POST = async (req: Request) => {
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter: new ExperimentalEmptyAdapter(), // the agent IS Hermes; no extra LLM adapter needed
    endpoint: "/api/copilotkit",
  });
  return handleRequest(req);
};
```

**2. UI** — any page:

```tsx
"use client";
import { CopilotKit } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import "@copilotkit/react-ui/styles.css";

export default function Page() {
  return (
    <CopilotKit runtimeUrl="/api/copilotkit" agent="hermes">
      <CopilotChat labels={{ title: "Hermes", initial: "Ask Hermes anything." }} />
    </CopilotKit>
  );
}
```

```bash
npm i @copilotkit/react-core @copilotkit/react-ui @copilotkit/runtime @ag-ui/client
```

(For the React/Next side, the repo's `copilotkit` skill scaffolds the provider +
route + theming with the version/bundling gotchas pre-solved.)

## What's mapped

| Hermes (`AIAgent` callback)              | AG-UI events emitted                                   |
| ---------------------------------------- | ------------------------------------------------------ |
| `stream_delta_callback(text)`            | `TEXT_MESSAGE_START` → `…CONTENT`(delta) → `…END`       |
| `tool_start_callback(id, name, args)`    | `TOOL_CALL_START` → `TOOL_CALL_ARGS` → `TOOL_CALL_END`  |
| `tool_complete_callback(id, …, result)`  | `TOOL_CALL_RESULT`                                      |
| turn lifecycle                           | `RUN_STARTED` … `RUN_FINISHED` / `RUN_ERROR`           |

> Note: `stream_delta_callback` carries token-level deltas (and `None` at end of a
> text segment); tool callbacks carry the model's real tool-call IDs. If a provider
> doesn't stream deltas, the run's `final_response` is emitted as one text message.

History is kept server-side per `threadId` (one persistent `AIAgent` each), which
preserves prompt caching across turns.

## Not yet wired (v2 ideas)

- **Frontend tools / HITL** — CopilotKit `useCopilotAction` tools arrive in
  `RunAgentInput.tools`; surfacing them to Hermes as callable tools (and routing
  approvals back) would enable human-in-the-loop. The plumbing point is
  `run()` in `server.py` (read `input_data.tools`) + an approval bridge like
  `acp_adapter/permissions.py`.
- **Shared state** — emit `STATE_SNAPSHOT` / `STATE_DELTA` to sync agent state
  into the UI (`useCoAgentState`).
- **Reasoning** — `thinking_callback` is currently dropped; map it to AG-UI
  `REASONING_*` events to show Hermes' thinking.
