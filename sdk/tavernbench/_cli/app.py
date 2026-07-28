"""
TavernBench CLI — entry point for `tavernbench` binary.

Install with:  pip install tavernbench[cli]
               uv tool install "tavernbench[cli]"
"""

import typer

app = typer.Typer(name="tavernbench", help="TavernBench SDK CLI — evaluate AI agents in a DnD dungeon crawler")


@app.command()
def version():
    """Print SDK version."""
    from tavernbench import __version__
    typer.echo(__version__)


@app.command()
def play(
    api_key: str = typer.Option(..., envvar="TAVERNBENCH_API_KEY", help="TavernBench API key"),
    server: str = typer.Option("ws://tavernbench.dkta.dev:4100", envvar="TAVERNBENCH_SERVER", help="WebSocket server URL"),
    zone: str = typer.Option("lobby", help="Starting zone"),
):
    """(Placeholder) Interactive spectator / manual play loop."""
    typer.echo("play not yet implemented")


@app.command()
def mcp(
    api_key: str = typer.Option(..., envvar="TAVERNBENCH_API_KEY", help="TavernBench API key"),
    server: str = typer.Option("ws://tavernbench.dkta.dev:4100", envvar="TAVERNBENCH_SERVER", help="WebSocket server URL"),
    zone: str = typer.Option("lobby", help="Starting zone"),
    transport: str = typer.Option("stdio", help="Transport mode: stdio or sse"),
):
    """Start the TavernBench MCP server."""
    try:
        from tavernbench._mcp.server import run_server
    except ImportError:
        typer.echo("mcp extra not installed. Run: pip install tavernbench[mcp]", err=True)
        raise typer.Exit(1)
    run_server(api_key=api_key, server=server, zone=zone, transport=transport)


def main():
    app()
