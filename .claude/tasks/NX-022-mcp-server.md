# NX-022 — MCP Server + Tool Schema Generation

**Track**: Infra (discoverability)
**Priority**: HIGH — enables any MCP client to use Nexus without training data
**Effort**: Medium
**Depends on**: All existing commands (wraps them)

---

## Problem

When an agent is told to use Playwright, it already knows the API from training data. With Nexus, agents are blind — they don't know what commands exist, what args they take, or what they return. This makes Nexus unusable as a tool provider for any external AI agent.

## Solution

Two deliverables:

### 1. MCP Server (`nexus/mcp_server.py`)
- FastMCP server exposing all 39 Nexus commands as MCP tools
- Each tool has typed parameters (auto-generates JSON Schema) and rich docstrings
- Screenshot returns `ImageContent` (inline base64 PNG)
- COM-using tools call `pythoncom.CoInitialize()` per-call (threadpool safety)
- Config in `.mcp.json` — Claude Code auto-discovers on restart

### 2. Tool Schema CLI (`nexus describe-tools`)
- `--fmt openai` — JSON Schema tool definitions (OpenAI function calling format)
- `--fmt markdown` — human/LLM-readable grouped reference
- `--output path` — write to file for system prompt injection

## Files

| File | Action |
|------|--------|
| `nexus/mcp_server.py` | Created — FastMCP server, 39 tools |
| `nexus/tools_schema.py` | Created — schema extraction from argparse |
| `nexus/run.py` | Modified — added `describe-tools` subcommand |
| `.mcp.json` | Modified — added nexus server entry |

## Usage

```bash
# CLI schema generation
python -m nexus describe-tools                    # OpenAI JSON format
python -m nexus describe-tools --fmt markdown     # Human-readable reference

# MCP server (started automatically by Claude Code via .mcp.json)
python -m nexus.mcp_server
```

## Status: DONE
