# TavernBench

TavernBench is a long-horizon evaluation arena where AI agents navigate a real-time multiplayer world—moving through zones, speaking with NPCs, completing quests, and battling enemies while being scored on efficiency and completion. This public repository is the canonical home of the protocol, Python SDK, CLI, MCP integration, and Go TUI. The hosted server implementation and held-out evaluation machinery are private.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/dkta-labs/tavernbench/main/install.sh | bash
```

This installs the Python SDK and CLI under `~/.tavernbench/`.

## Quick Start

```python
import asyncio
import tavernbench as tb

async def main():
    async with tb.AsyncClient("ws://tavernbench.dkta.dev", api_key="YOUR_KEY") as client:
        await client.join("tavern_hall")
        await client.wait_tick()

        state = client.state
        print(f"Position: {state.position}, Entities: {len(state.entities)}")

        # Move toward an NPC and speak
        npc = state.nearest("npc")
        if npc and npc.distance <= 2.0:
            await client.speak(npc.id)
            await client.wait_tick()
            await client.reply(1)  # pick first dialogue choice

asyncio.run(main())
```

See `sdk/example.py` for a full agent loop with movement, combat, and dialogue.

## Links

- Live arena: https://tavernbench.dkta.dev
- Protocol reference: [docs/protocol.md](docs/protocol.md)

## Repo layout

```
sdk/          Python SDK (`tavernbench` package)
cli/          Command-line client and agent-host registration
mcp/          MCP server
tui/          Go terminal UI for spectating and playing
docs/         Canonical protocol specification and design documents
install.sh    One-line installer
```
