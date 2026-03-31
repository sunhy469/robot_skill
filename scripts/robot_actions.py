from __future__ import annotations

import os
from typing import Any, Dict, Optional

from robot_core import (
    agv_goto_location,
    consume_token,
    ensure_ready,
    ensure_token_ready,
    extract_camera_jpg_path,
    fetch_image_bytes,
    finalize_robot,
    generate_token,
    get_camera_jpg,
    get_current_location,
    grip_close,
    grip_open,
    grip_position,
    initialize_robot,
    load_state,
    perform,
    reset_robot,
    reset_state_file,
    return_to_safe,
    save_state,
    shutdown_robot,
    vehicle_home,
    vehicle_reset,
    vehicle_stop,
)


def cmd_init_all() -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    token_resp = generate_token(forced=1)
    token = token_resp.get("data", {}).get("token", "")
    result["generate_token"] = token_resp

    try:
        result["vehicle_reset"] = vehicle_reset(token)
    except Exception as e:
        result["vehicle_reset_error"] = str(e)

    try:
        result["reset_robot"] = reset_robot(token, recover=1, clear=1)
    except Exception as e:
        result["reset_robot_error"] = str(e)

    result["initialize_robot"] = initialize_robot(token, homed=1, forced=0)
    result["state"] = save_state(token=token, initialized=True)
    return result


def cmd_camera(save_path: Optional[str] = None) -> Dict[str, Any]:
    token = ensure_ready()
    camera_data = get_camera_jpg(token)
    jpg_path = extract_camera_jpg_path(camera_data)

    result: Dict[str, Any] = {"camera_response": camera_data, "jpg_path": jpg_path}

    if save_path is None:
        references_dir = os.path.join(os.path.dirname(__file__), "..", "references")
        os.makedirs(references_dir, exist_ok=True)
        save_path = os.path.join(references_dir, "current_view.jpg")

    content = fetch_image_bytes(jpg_path)
    with open(save_path, "wb") as f:
        f.write(content)
    result["saved_to"] = save_path
    return result


def cmd_close_robot() -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    state = load_state()
    token = state.get("token", "") or ""

    if token:
        try:
            result["finalize_robot"] = finalize_robot(token)
        except Exception as e:
            result["finalize_robot_error"] = str(e)

        try:
            result["consume_token"] = consume_token(token)
        except Exception as e:
            result["consume_token_error"] = str(e)
    else:
        result["info"] = "本地状态中没有 token，跳过 finalize 和 consume。"

    result["state_reset"] = reset_state_file()
    return result


def cmd_grip_open() -> Dict[str, Any]:
    return grip_open(ensure_ready())


def cmd_grip_close() -> Dict[str, Any]:
    return grip_close(ensure_ready())


def cmd_grip_position(value: int) -> Dict[str, Any]:
    return grip_position(ensure_ready(), value)


def cmd_perform(target: str, vel: int, acc: int, wait: int) -> Dict[str, Any]:
    return perform(ensure_ready(), target=target, vel=vel, acc=acc, wait=wait)


def cmd_safe(target: str) -> Dict[str, Any]:
    return return_to_safe(ensure_ready(), target=target)


def cmd_shutdown() -> Dict[str, Any]:
    token = ensure_token_ready()
    result = shutdown_robot(token)
    save_state(token=token, initialized=False)
    return result


def cmd_status() -> Dict[str, Any]:
    return load_state()


def cmd_agv_goto_location(location: str) -> Dict[str, Any]:
    return agv_goto_location(ensure_ready(), location)


def cmd_vehicle_stop() -> Dict[str, Any]:
    return vehicle_stop(ensure_ready())


def cmd_vehicle_home() -> Dict[str, Any]:
    return vehicle_home(ensure_ready())


def cmd_get_current_location() -> Dict[str, Any]:
    return get_current_location(ensure_ready())
