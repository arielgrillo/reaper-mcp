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
def get_track_routing(track_index: int) -> dict:
    """Return sends, receives, and hardware outputs for one track."""
    return send_reaper_command(
        "get_track_routing",
        track_index=track_index
    )

@mcp.tool()
def get_markers_regions() -> dict:
    """Return timeline-ordered markers and regions from the current project."""
    return send_reaper_command("get_markers_regions")

@mcp.tool()
def get_tempo_map() -> dict:
    """Return explicit tempo and time-signature changes in timeline order."""
    return send_reaper_command("get_tempo_map")

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
def diagnose_fx_parameter_formatter(
    track_index: int,
    fx_index: int,
    parameter_index: int
) -> dict:
    """Sample REAPER's normalized formatter for one FX parameter."""
    return send_reaper_command(
        "diagnose_fx_parameter_formatter",
        track_index=track_index,
        fx_index=fx_index,
        parameter_index=parameter_index
    )

@mcp.tool()
def set_fx_parameter(
    track_index: int,
    fx_index: int,
    parameter_index: int,
    normalized_value: float | None = None,
    formatted_value: str | None = None
) -> dict:
    """Set one FX parameter from a normalized or formatted value."""
    return send_reaper_command(
        "set_fx_parameter",
        track_index=track_index,
        fx_index=fx_index,
        parameter_index=parameter_index,
        normalized_value=normalized_value,
        formatted_value=formatted_value
    )

@mcp.tool()
def set_fx_parameter_formatted(
    track_index: int,
    fx_index: int,
    parameter_index: int,
    formatted_value: str
) -> dict:
    """Set one FX parameter from its human-readable formatted value."""
    return send_reaper_command(
        "set_fx_parameter",
        track_index=track_index,
        fx_index=fx_index,
        parameter_index=parameter_index,
        formatted_value=formatted_value
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
