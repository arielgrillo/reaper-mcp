# pyright: reportUndefinedVariable=false

import socket
import json
import math
import re

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

def get_musical_position(position_seconds):
    beat_info = RPR_TimeMap2_timeToBeats(
        0,
        position_seconds,
        0,
        0,
        0.0,
        0
    )

    beat_within_measure = beat_info[0]
    measure = beat_info[3]
    measure_length = beat_info[4]
    full_beats = beat_info[5]
    denominator = beat_info[6]

    return {
        "position_beats": full_beats,
        "musical_position": {
            "measure": measure + 1,
            "beat": full_beats,
            "beat_within_measure": beat_within_measure + 1,
            "time_signature": {
                "numerator": measure_length,
                "denominator": denominator
            }
        }
    }

def handle_get_tempo_map(request):
    events = []
    marker_count = RPR_CountTempoTimeSigMarkers(0)

    for reaper_index in range(marker_count):
        marker_info = RPR_GetTempoTimeSigMarker(
            0,
            reaper_index,
            0.0,
            0,
            0.0,
            0.0,
            0,
            0,
            False
        )

        if not marker_info[0]:
            continue

        position_seconds = marker_info[3]
        effective_time_signature = RPR_TimeMap_GetTimeSigAtTime(
            0,
            position_seconds,
            0,
            0,
            0.0
        )
        musical = get_musical_position(position_seconds)

        events.append({
            "index": reaper_index + 1,
            "position_seconds": position_seconds,
            "bpm": marker_info[6],
            "numerator": effective_time_signature[2],
            "denominator": effective_time_signature[3],
            "marker_numerator": marker_info[7],
            "marker_denominator": marker_info[8],
            "linear_tempo_change": bool(marker_info[9]),
            "position_beats": musical["position_beats"],
            "musical_position": musical["musical_position"]
        })

    return {
        "events": events
    }

def handle_get_markers_regions(request):
    markers = []
    regions = []
    marker_region_count = RPR_CountProjectMarkers(0, 0, 0)[0]

    for enumeration_index in range(marker_region_count):
        marker_info = RPR_EnumProjectMarkers3(
            0,
            enumeration_index,
            False,
            0.0,
            0.0,
            "",
            0,
            0
        )

        if not marker_info[0]:
            continue

        is_region = bool(marker_info[3])
        position_seconds = marker_info[4]
        end_seconds = marker_info[5]
        name = marker_info[6]
        project_number = marker_info[7]
        color = marker_info[8]

        if is_region:
            start_musical = get_musical_position(position_seconds)
            end_musical = get_musical_position(end_seconds)

            regions.append({
                "index": enumeration_index + 1,
                "enumeration_index": enumeration_index,
                "region_number": project_number,
                "name": name,
                "start_seconds": position_seconds,
                "end_seconds": end_seconds,
                "duration_seconds": end_seconds - position_seconds,
                "start_beats": start_musical["position_beats"],
                "end_beats": end_musical["position_beats"],
                "start_musical_position": (
                    start_musical["musical_position"]
                ),
                "end_musical_position": end_musical["musical_position"],
                "color": color,
                "is_region": True
            })
        else:
            musical = get_musical_position(position_seconds)

            markers.append({
                "index": enumeration_index + 1,
                "enumeration_index": enumeration_index,
                "marker_number": project_number,
                "name": name,
                "position_seconds": position_seconds,
                "position_beats": musical["position_beats"],
                "musical_position": musical["musical_position"],
                "color": color,
                "is_region": False
            })

    return {
        "markers": markers,
        "regions": regions
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

def resolve_track_fx(request):
    track_index = request.get("track_index")
    fx_index = request.get("fx_index")

    if not isinstance(track_index, int) or isinstance(track_index, bool):
        return None, {
            "error": "track_index must be a 1-based integer"
        }

    track_count = RPR_CountTracks(0)

    if track_index < 1 or track_index > track_count:
        return None, {
            "error": (
                f"Track index {track_index} is out of range; "
                f"project has {track_count} tracks"
            )
        }

    track = RPR_GetTrack(0, track_index - 1)

    if not isinstance(fx_index, int) or isinstance(fx_index, bool):
        return None, {
            "error": "fx_index must be a 1-based integer"
        }

    fx_count = RPR_TrackFX_GetCount(track)

    if fx_index < 1 or fx_index > fx_count:
        return None, {
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

    return {
        "track_index": track_index,
        "track": track,
        "track_name": track_name,
        "fx_index": fx_index,
        "reaper_fx_index": reaper_fx_index,
        "fx_name": fx_name
    }, None

def get_fx_parameter_info(track, reaper_fx_index, parameter_index):
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

    return {
        "index": parameter_index + 1,
        "name": parameter_name_info[4],
        "value": parameter_value_info[0],
        "formatted_value": formatted_value_info[4],
        "min_value": parameter_value_info[4],
        "max_value": parameter_value_info[5],
        "mid_value": parameter_value_info[6]
    }

def normalize_formatted_value(value):
    return " ".join(value.split()).casefold()

def parse_formatted_number(value):
    normalized_value = normalize_formatted_value(value)
    matches = list(re.finditer(
        r"[-+]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:e[-+]?\d+)?",
        normalized_value
    ))

    if len(matches) != 1:
        return None

    match = matches[0]
    number_text = match.group(0).replace(",", ".")

    if "e" in number_text:
        mantissa, exponent_text = number_text.split("e", 1)
        exponent = int(exponent_text)
    else:
        mantissa = number_text
        exponent = 0

    decimal_places = (
        len(mantissa.split(".", 1)[1])
        if "." in mantissa
        else 0
    )

    try:
        number = float(number_text)
    except ValueError:
        return None

    if not math.isfinite(number):
        return None

    tolerance = 0.5 * (10 ** (exponent - decimal_places))

    return number, tolerance

def formatted_numbers_match(target_number, formatted_number_info):
    formatted_number, formatted_tolerance = formatted_number_info

    return (
        abs(formatted_number - target_number)
        <= formatted_tolerance + 1e-12
    )

def format_fx_parameter_normalized(
    track,
    reaper_fx_index,
    reaper_parameter_index,
    normalized_value
):
    formatted_value_info = RPR_TrackFX_FormatParamValueNormalized(
        track,
        reaper_fx_index,
        reaper_parameter_index,
        normalized_value,
        "",
        512
    )

    if not formatted_value_info[0]:
        return None

    return formatted_value_info[5]

def resolve_formatted_fx_parameter(
    track,
    reaper_fx_index,
    reaper_parameter_index,
    requested_formatted_value
):
    parsed_target = parse_formatted_number(requested_formatted_value)

    if parsed_target is None:
        return None

    target_number, _ = parsed_target
    sample_count = 64
    samples = []

    for sample_index in range(sample_count + 1):
        normalized_value = sample_index / sample_count
        formatted_value = format_fx_parameter_normalized(
            track,
            reaper_fx_index,
            reaper_parameter_index,
            normalized_value
        )

        if formatted_value is None:
            return None

        parsed_formatted_value = parse_formatted_number(formatted_value)

        if parsed_formatted_value is None:
            return None

        if formatted_numbers_match(target_number, parsed_formatted_value):
            return normalized_value

        samples.append((
            normalized_value,
            parsed_formatted_value
        ))

    for sample_index in range(sample_count):
        low_normalized, low_parsed = samples[sample_index]
        high_normalized, high_parsed = samples[sample_index + 1]

        if low_parsed is None or high_parsed is None:
            continue

        low_number, _ = low_parsed
        high_number, _ = high_parsed

        if (
            low_number == high_number
            or target_number < min(low_number, high_number)
            or target_number > max(low_number, high_number)
        ):
            continue

        is_increasing = high_number > low_number

        for _ in range(40):
            middle_normalized = (
                low_normalized + high_normalized
            ) / 2
            middle_formatted = format_fx_parameter_normalized(
                track,
                reaper_fx_index,
                reaper_parameter_index,
                middle_normalized
            )

            if middle_formatted is None:
                return None

            middle_parsed = parse_formatted_number(middle_formatted)

            if middle_parsed is None:
                break

            if formatted_numbers_match(target_number, middle_parsed):
                return middle_normalized

            middle_number, _ = middle_parsed

            if (middle_number < target_number) == is_increasing:
                low_normalized = middle_normalized
            else:
                high_normalized = middle_normalized

    return None

def handle_get_fx_parameters(request):
    fx_context, error = resolve_track_fx(request)

    if error is not None:
        return error

    track = fx_context["track"]
    reaper_fx_index = fx_context["reaper_fx_index"]

    parameter_count = RPR_TrackFX_GetNumParams(
        track,
        reaper_fx_index
    )
    parameters = []

    for parameter_index in range(parameter_count):
        parameters.append(get_fx_parameter_info(
            track,
            reaper_fx_index,
            parameter_index
        ))

    return {
        "track_index": fx_context["track_index"],
        "track_name": fx_context["track_name"],
        "fx_index": fx_context["fx_index"],
        "fx_name": fx_context["fx_name"],
        "parameter_count": parameter_count,
        "parameters": parameters
    }

def resolve_fx_parameter(request):
    fx_context, error = resolve_track_fx(request)

    if error is not None:
        return None, error

    parameter_index = request.get("parameter_index")

    if (
        not isinstance(parameter_index, int)
        or isinstance(parameter_index, bool)
    ):
        return None, {
            "error": "parameter_index must be a 1-based integer"
        }

    parameter_count = RPR_TrackFX_GetNumParams(
        fx_context["track"],
        fx_context["reaper_fx_index"]
    )

    if parameter_index < 1 or parameter_index > parameter_count:
        return None, {
            "error": (
                f"Parameter index {parameter_index} is out of range; "
                f"FX {fx_context['fx_index']} has "
                f"{parameter_count} parameters"
            )
        }

    fx_context["parameter_index"] = parameter_index
    fx_context["reaper_parameter_index"] = parameter_index - 1

    return fx_context, None

def handle_get_fx_parameter(request):
    parameter_context, error = resolve_fx_parameter(request)

    if error is not None:
        return error

    parameter = get_fx_parameter_info(
        parameter_context["track"],
        parameter_context["reaper_fx_index"],
        parameter_context["reaper_parameter_index"]
    )

    return {
        "track_index": parameter_context["track_index"],
        "track_name": parameter_context["track_name"],
        "fx_index": parameter_context["fx_index"],
        "fx_name": parameter_context["fx_name"],
        "parameter_index": parameter["index"],
        "parameter_name": parameter["name"],
        "value": parameter["value"],
        "formatted_value": parameter["formatted_value"],
        "min_value": parameter["min_value"],
        "max_value": parameter["max_value"],
        "mid_value": parameter["mid_value"]
    }

def handle_diagnose_fx_parameter_formatter(request):
    parameter_context, error = resolve_fx_parameter(request)

    if error is not None:
        return error

    parameter = get_fx_parameter_info(
        parameter_context["track"],
        parameter_context["reaper_fx_index"],
        parameter_context["reaper_parameter_index"]
    )
    samples = []

    for sample_index in range(11):
        normalized_value = sample_index / 10
        formatted_value_info = RPR_TrackFX_FormatParamValueNormalized(
            parameter_context["track"],
            parameter_context["reaper_fx_index"],
            parameter_context["reaper_parameter_index"],
            normalized_value,
            "",
            512
        )

        samples.append({
            "normalized_value": normalized_value,
            "formatter_success": bool(formatted_value_info[0]),
            "formatted_value": formatted_value_info[5]
        })

    return {
        "track_index": parameter_context["track_index"],
        "track_name": parameter_context["track_name"],
        "fx_index": parameter_context["fx_index"],
        "fx_name": parameter_context["fx_name"],
        "parameter_index": parameter["index"],
        "parameter_name": parameter["name"],
        "samples": samples
    }

def handle_set_fx_parameter(request):
    parameter_context, error = resolve_fx_parameter(request)

    if error is not None:
        return error

    normalized_value = request.get("normalized_value")
    formatted_value = request.get("formatted_value")
    has_normalized_value = normalized_value is not None
    has_formatted_value = formatted_value is not None

    if has_normalized_value == has_formatted_value:
        return {
            "error": (
                "Exactly one of normalized_value or formatted_value "
                "must be provided"
            )
        }

    if has_normalized_value:
        if (
            not isinstance(normalized_value, (int, float))
            or isinstance(normalized_value, bool)
            or not math.isfinite(normalized_value)
        ):
            return {
                "error": (
                    "normalized_value must be a finite number "
                    "from 0.0 to 1.0"
                )
            }

        if normalized_value < 0.0 or normalized_value > 1.0:
            return {
                "error": (
                    f"Normalized value {normalized_value} is out "
                    "of range; expected 0.0 to 1.0"
                )
            }

        input_mode = "normalized"
        resolved_normalized_value = float(normalized_value)

    else:
        if (
            not isinstance(formatted_value, str)
            or not formatted_value.strip()
        ):
            return {
                "error": "formatted_value must be a non-empty string"
            }

        input_mode = "formatted"
        resolved_normalized_value = resolve_formatted_fx_parameter(
            parameter_context["track"],
            parameter_context["reaper_fx_index"],
            parameter_context["reaper_parameter_index"],
            formatted_value
        )

        if resolved_normalized_value is None:
            return {
                "error": (
                    "formatted_value could not be resolved reliably; "
                    "only continuous parameters with a single numeric "
                    "formatted value are supported"
                )
            }

    write_succeeded = RPR_TrackFX_SetParamNormalized(
        parameter_context["track"],
        parameter_context["reaper_fx_index"],
        parameter_context["reaper_parameter_index"],
        resolved_normalized_value
    )

    if not write_succeeded:
        return {
            "error": "REAPER failed to set the FX parameter"
        }

    try:
        applied_value = RPR_TrackFX_GetParamNormalized(
            parameter_context["track"],
            parameter_context["reaper_fx_index"],
            parameter_context["reaper_parameter_index"]
        )
        parameter = get_fx_parameter_info(
            parameter_context["track"],
            parameter_context["reaper_fx_index"],
            parameter_context["reaper_parameter_index"]
        )
    except Exception as read_back_error:
        return {
            "error": (
                "Failed to read back the FX parameter: "
                f"{read_back_error}"
            )
        }

    if (
        not isinstance(applied_value, (int, float))
        or isinstance(applied_value, bool)
        or not math.isfinite(applied_value)
        or applied_value < 0.0
        or applied_value > 1.0
    ):
        return {
            "error": "REAPER returned an invalid parameter read-back value"
        }

    canonical_formatted_value = None

    if input_mode == "formatted":
        requested_formatted_number = parse_formatted_number(
            formatted_value
        )
        read_back_formatted_number = parse_formatted_number(
            parameter["formatted_value"]
        )
        canonical_formatted_value = format_fx_parameter_normalized(
            parameter_context["track"],
            parameter_context["reaper_fx_index"],
            parameter_context["reaper_parameter_index"],
            applied_value
        )
        canonical_formatted_number = (
            parse_formatted_number(canonical_formatted_value)
            if canonical_formatted_value is not None
            else None
        )

        if (
            requested_formatted_number is None
            or read_back_formatted_number is None
            or canonical_formatted_number is None
        ):
            return {
                "error": (
                    "REAPER returned an unparseable formatted "
                    "read-back value"
                )
            }

        requested_number, _ = requested_formatted_number

        if (
            not formatted_numbers_match(
                requested_number,
                read_back_formatted_number
            )
            or not formatted_numbers_match(
                requested_number,
                canonical_formatted_number
            )
        ):
            return {
                "error": (
                    "REAPER formatted read-back did not match the "
                    "requested numeric value"
                )
            }

    response = {
        "track_index": parameter_context["track_index"],
        "track_name": parameter_context["track_name"],
        "fx_index": parameter_context["fx_index"],
        "fx_name": parameter_context["fx_name"],
        "parameter_index": parameter["index"],
        "parameter_name": parameter["name"],
        "input_mode": input_mode,
        "resolved_normalized_value": resolved_normalized_value,
        "applied_value": applied_value,
        "formatted_value": parameter["formatted_value"],
        "success": True
    }

    if input_mode == "normalized":
        response["requested_normalized_value"] = float(normalized_value)
    else:
        response["requested_formatted_value"] = formatted_value
        response["canonical_formatted_value"] = (
            canonical_formatted_value
        )

    return response

def handle_get_fx_presets(request):
    fx_context, error = resolve_track_fx(request)

    if error is not None:
        return error

    current_preset_info = RPR_TrackFX_GetPreset(
        fx_context["track"],
        fx_context["reaper_fx_index"],
        "",
        1024
    )
    preset_index_info = RPR_TrackFX_GetPresetIndex(
        fx_context["track"],
        fx_context["reaper_fx_index"],
        0
    )

    return {
        "track_index": fx_context["track_index"],
        "track_name": fx_context["track_name"],
        "fx_index": fx_context["fx_index"],
        "fx_name": fx_context["fx_name"],
        "current_preset": (
            current_preset_info[3]
            if current_preset_info[0]
            else None
        ),
        "preset_count": preset_index_info[3]
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
    "get_tempo_map": handle_get_tempo_map,
    "get_markers_regions": handle_get_markers_regions,
    "get_tracks": handle_get_tracks,
    "get_track_fx": handle_get_track_fx,
    "get_fx_parameters": handle_get_fx_parameters,
    "get_fx_parameter": handle_get_fx_parameter,
    "get_fx_presets": handle_get_fx_presets,
    "diagnose_fx_parameter_formatter": (
        handle_diagnose_fx_parameter_formatter
    ),
    "set_fx_parameter": handle_set_fx_parameter,
}

loop()
