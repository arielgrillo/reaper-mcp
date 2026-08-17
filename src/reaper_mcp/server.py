import json
import socket

from mcp.server.mcpserver import MCPServer


HOST = "127.0.0.1"
PORT = 8765

mcp = MCPServer("reaper-mcp")


def send_reaper_command(command: str, **arguments) -> dict:
    with socket.create_connection((HOST, PORT), timeout=2) as sock:
        request = {
            "command": command,
            **arguments
        }

        sock.sendall(json.dumps(request).encode("utf-8"))

        response = sock.recv(4096)

        return json.loads(response.decode("utf-8"))


@mcp.tool()
def get_tracks() -> dict:
    """Return tracks from the current REAPER project."""
    return send_reaper_command("get_tracks")

@mcp.tool()
def get_track_fx() -> dict:
    """Return the FX chains for all tracks in the current REAPER project."""
    return send_reaper_command("get_track_fx")

@mcp.tool()
def get_fx_parameters(track_index: int, fx_index: int) -> dict:
    """Return parameters for one FX on a track in the current REAPER project."""
    return send_reaper_command(
        "get_fx_parameters",
        track_index=track_index,
        fx_index=fx_index
    )

@mcp.tool()
def ping() -> str:
    """Simple MCP connectivity test."""
    return "pong"

@mcp.tool()
def get_track_count() -> int:
    """Return the number of tracks in the current REAPER project."""
    response = send_reaper_command("get_track_count")
    return response["track_count"]

@mcp.tool()
def get_project_info() -> dict:
    """Return basic information about the current REAPER project."""
    return send_reaper_command("get_project_info")

if __name__ == "__main__":
    mcp.run(transport="stdio")
