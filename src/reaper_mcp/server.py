import json
import socket

from mcp.server.mcpserver import MCPServer


HOST = "127.0.0.1"
PORT = 8765
BRIDGE_TIMEOUT = 30

mcp = MCPServer("reaper-mcp")


def send_reaper_command(command: str, **arguments) -> dict:
    with socket.create_connection(
        (HOST, PORT),
        timeout=BRIDGE_TIMEOUT
    ) as sock:
        request = {
            "command": command,
            **arguments
        }

        sock.sendall(json.dumps(request).encode("utf-8"))

        response_chunks = []

        while True:
            chunk = sock.recv(4096)

            if not chunk:
                break

            response_chunks.append(chunk)

        response = b"".join(response_chunks)

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
def get_fx_parameter(
    track_index: int,
    fx_index: int,
    parameter_index: int
) -> dict:
    """Return one parameter for one FX in the current REAPER project."""
    return send_reaper_command(
        "get_fx_parameter",
        track_index=track_index,
        fx_index=fx_index,
        parameter_index=parameter_index
    )

@mcp.tool()
def get_fx_presets(track_index: int, fx_index: int) -> dict:
    """Return current preset information for one FX."""
    return send_reaper_command(
        "get_fx_presets",
        track_index=track_index,
        fx_index=fx_index
    )

@mcp.tool()
def set_fx_parameter(
    track_index: int,
    fx_index: int,
    parameter_index: int,
    value: float
) -> dict:
    """Set one normalized FX parameter and return its applied value."""
    return send_reaper_command(
        "set_fx_parameter",
        track_index=track_index,
        fx_index=fx_index,
        parameter_index=parameter_index,
        value=value
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
