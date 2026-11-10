# Q&A tool-trace expandable panes — Design Spec

**Date:** 2026-09-26  
**Status:** Approved for implementation  
**Parent:** `2026-09-24-standalone-qa-agent-design.md`

## Goal

Under each Q&A assistant reply, show ChatGPT/Claude-style collapsible **Used tools** chips. Expanding a chip reveals three panes parsed from the Cortex MCP tool payload:

1. MCP query  
2. Analyst interpretation  
3. Response  

## Locked decisions

| Topic | Choice |
|---|---|
| Interaction | Collapsible chips under the assistant message (not inline answer citations) |
| Trace content | Parse Cortex MCP tool result (no second LLM summarize pass) |
| Incomplete payloads | Still expand; missing sections show `Not returned by Cortex` |
| API shape | Extend `sources[]` with optional `query` / `interpretation` / `response` |

## Contract

```json
{
  "answer": "…",
  "sources": [
    {
      "label": "sv_hr_workforce",
      "detail": "short summary for collapsed chip",
      "query": "…",
      "interpretation": "…",
      "response": "…"
    }
  ]
}
```

- Tool sources always include the three string fields (sentinel when missing).
- Non-tool sources (errors / offline) may omit the three fields; UI does not show the three-pane body.

## Backend

- Pair AIMessage `tool_calls` args with matching ToolMessage results.
- `query`: prefer tool args `message` / `question` / `query` / `prompt` / `input`; else parse from result if present.
- `interpretation` / `response`: parse common Cortex JSON keys (`interpretation`, `sql`, `query`, `results`, `data`, `content`, etc.).
- Preserve `detail` as a short truncated summary for the closed chip.

## UI

- Replace flat Sources list with **Used tools** strip of `<button>` chips (`aria-expanded`).
- Expand inline accordion under the chip; multiple chips may be open.
- Three labeled scrollable pre blocks; fit existing Q&A styles.

## Out of scope

- Streaming tool traces  
- Parallel `toolTraces[]` array  
- Changing triage email QA node UI  
