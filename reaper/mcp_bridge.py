# pyright: reportUndefinedVariable=false

import socket
import json
import math

HOST = "127.0.0.1"
PORT = 8765

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen(1)
server.setblocking(False)

RPR_ShowConsoleMsg("REAPER MCP bridge listening on 127.0.0.1:8765\n")


def process_request(data):
    request = json.loads(data)

    command = request.get("command")

    handler = COMMAND_HANDLERS.get(command)

    if handler is None:
        return {
            "error": f"Unknown command: {command}"
        }

    return handler(request)

def linear_to_db(value: float) -> float | None:
    if value <= 0:
        return None

    return 20 * math.log10(value)

def get_pan_info(value: float) -> dict:
    if value < 0:
        direction = "L"
    elif value > 0:
        direction = "R"
    else:
        direction = "C"

    return {
        "pan": value,
        "pan_percent": round(abs(value) * 100, 1),
        "pan_direction": direction
    }

def handle_get_track_count(request):
    return {
        "track_count": RPR_CountTracks(0)
    }

def handle_get_project_info(request):
    project_info = RPR_GetSetProjectInfo_String(
        0,
        "PROJECT_NAME",
        "",
        False
    )

    project_name = project_info[3]

    time_signature = RPR_GetProjectTimeSignature2(
        0,
        0,
        0
    )

    bpm = time_signature[1]

    play_state_value = RPR_GetPlayState()

    if play_state_value & 4:
        play_state = "recording"
    elif play_state_value & 1:
        play_state = "playing"
    elif play_state_value & 2:
        play_state = "paused"
    else:
        play_state = "stopped"

    return {
        "project_name": project_name,
        "track_count": RPR_CountTracks(0),
        "tempo": bpm,
        "play_state": play_state
    }

def handle_get_tracks(request):
    tracks = []
    folder_stack = []

    track_count = RPR_CountTracks(0)

    for index in range(track_count):
        track = RPR_GetTrack(0, index)

        track_name_info = RPR_GetTrackName(track, "", 512)
        track_name = track_name_info[2]

        muted = bool(
            RPR_GetMediaTrackInfo_Value(track, "B_MUTE")
        )

        solo_value = RPR_GetMediaTrackInfo_Value(track, "I_SOLO")
        solo = solo_value > 0

        volume = RPR_GetMediaTrackInfo_Value(track, "D_VOL")
        volume_db = linear_to_db(volume)

        pan = RPR_GetMediaTrackInfo_Value(track, "D_PAN")
        pan_info = get_pan_info(pan)

        folder_depth = int(
            RPR_GetMediaTrackInfo_Value(track, "I_FOLDERDEPTH")
        )

        parent_index = None
        parent_name = None

        if folder_stack:
            parent_index = folder_stack[-1]["index"]
            parent_name = folder_stack[-1]["name"]

        tracks.append({
            "index": index + 1,
            "name": track_name,
            "muted": muted,
            "solo": solo,
            "volume": volume,
            "volume_db": (
                round(volume_db, 2)
                if volume_db is not None
                else None
            ),
            **pan_info,
            "folder_depth": folder_depth,
            "is_folder": folder_depth > 0,
            "is_nested": parent_index is not None,
            "parent_index": parent_index,
            "parent_name": parent_name
        })

        if folder_depth > 0:
            folder_stack.append({
                "index": index + 1,
                "name": track_name
            })

        elif folder_depth < 0:
            for _ in range(abs(folder_depth)):
                if folder_stack:
                    folder_stack.pop()

    return {
        "tracks": tracks
    }

def handle_get_track_fx(request):
    tracks = []

    track_count = RPR_CountTracks(0)

    for track_index in range(track_count):
        track = RPR_GetTrack(0, track_index)

        track_name_info = RPR_GetTrackName(track, "", 512)
        track_name = track_name_info[2]

        fx = []
        fx_count = RPR_TrackFX_GetCount(track)

        for fx_index in range(fx_count):
            fx_name_info = RPR_TrackFX_GetFXName(
                track,
                fx_index,
                "",
                512
            )

            fx.append({
                "index": fx_index + 1,
                "name": fx_name_info[3],
                "enabled": bool(
                    RPR_TrackFX_GetEnabled(track, fx_index)
                ),
                "offline": bool(
                    RPR_TrackFX_GetOffline(track, fx_index)
                )
            })

        tracks.append({
            "track_index": track_index + 1,
            "track_name": track_name,
            "fx_count": fx_count,
            "fx": fx
        })

    return {
        "tracks": tracks
    }

def handle_get_fx_parameters(request):
    track_index = request.get("track_index")
    fx_index = request.get("fx_index")

    if not isinstance(track_index, int) or isinstance(track_index, bool):
        return {
            "error": "track_index must be a 1-based integer"
        }

    track_count = RPR_CountTracks(0)

    if track_index < 1 or track_index > track_count:
        return {
            "error": (
                f"Track index {track_index} is out of range; "
                f"project has {track_count} tracks"
            )
        }

    track = RPR_GetTrack(0, track_index - 1)

    if not isinstance(fx_index, int) or isinstance(fx_index, bool):
        return {
            "error": "fx_index must be a 1-based integer"
        }

    fx_count = RPR_TrackFX_GetCount(track)

    if fx_index < 1 or fx_index > fx_count:
        return {
            "error": (
                f"FX index {fx_index} is out of range; "
                f"track {track_index} has {fx_count} FX"
            )
        }

    reaper_fx_index = fx_index - 1

    track_name_info = RPR_GetTrackName(track, "", 512)
    track_name = track_name_info[2]

    fx_name_info = RPR_TrackFX_GetFXName(
        track,
        reaper_fx_index,
        "",
        512
    )
    fx_name = fx_name_info[3]

    parameter_count = RPR_TrackFX_GetNumParams(
        track,
        reaper_fx_index
    )
    parameters = []

    for parameter_index in range(parameter_count):
        parameter_name_info = RPR_TrackFX_GetParamName(
            track,
            reaper_fx_index,
            parameter_index,
            "",
            512
        )
        parameter_value_info = RPR_TrackFX_GetParamEx(
            track,
            reaper_fx_index,
            parameter_index,
            0.0,
            0.0,
            0.0
        )
        formatted_value_info = RPR_TrackFX_GetFormattedParamValue(
            track,
            reaper_fx_index,
            parameter_index,
            "",
            512
        )

        parameters.append({
            "index": parameter_index + 1,
            "name": parameter_name_info[4],
            "value": parameter_value_info[0],
            "formatted_value": formatted_value_info[4],
            "min_value": parameter_value_info[4],
            "max_value": parameter_value_info[5],
            "mid_value": parameter_value_info[6]
        })

    return {
        "track_index": track_index,
        "track_name": track_name,
        "fx_index": fx_index,
        "fx_name": fx_name,
        "parameter_count": parameter_count,
        "parameters": parameters
    }

def loop():
    try:
        client, address = server.accept()
        client.settimeout(0.1)

        data = client.recv(4096)

        if data:
            response = process_request(data.decode("utf-8"))
            client.sendall(json.dumps(response).encode("utf-8"))

        client.close()

    except BlockingIOError:
        pass
    except Exception as error:
        RPR_ShowConsoleMsg(f"MCP bridge error: {error}\n")

    RPR_defer("loop()")

COMMAND_HANDLERS = {
    "get_track_count": handle_get_track_count,
    "get_project_info": handle_get_project_info,
    "get_tracks": handle_get_tracks,
    "get_track_fx": handle_get_track_fx,
    "get_fx_parameters": handle_get_fx_parameters,
}

loop()
