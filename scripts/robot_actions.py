from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import robot_core as rc
from robot_core import RobotApiError


def parse_json_arg(text: Optional[str], arg_name: str) -> Any:
    if text is None:
        return None
    try:
        return json.loads(text)
    except Exception as e:
        raise RobotApiError(f"参数 {arg_name} JSON 解析失败: {e}") from e


def maybe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    return int(value)


def maybe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def drop_none_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in data.items() if v is not None}


def resolve_token(token: Optional[str] = None, require_ready: bool = False, require_initialized: bool = False) -> str:
    if token:
        return token
    if require_ready or require_initialized:
        return rc.ensure_ready()
    return rc.ensure_token_ready()


# ===== 旧命令：保持兼容 =====
def cmd_init_all() -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    token_resp = rc.generate_token(forced=1)
    token = token_resp.get("data", {}).get("token", "")
    result["generate_token"] = token_resp

    try:
        result["vehicle_reset"] = rc.vehicle_reset(token)
    except Exception as e:
        result["vehicle_reset_error"] = str(e)

    try:
        result["reset_robot"] = rc.reset_robot(token, recover=1, clear=1)
    except Exception as e:
        result["reset_robot_error"] = str(e)

    result["initialize_robot"] = rc.initialize_robot(token, homed=1, forced=0)
    result["state"] = rc.save_state(token=token, initialized=True)
    return result


def cmd_camera(save_path: Optional[str] = None) -> Dict[str, Any]:
    token = rc.ensure_ready()
    camera_data = rc.get_camera_jpg(token)
    jpg_path = rc.extract_camera_jpg_path(camera_data)

    result: Dict[str, Any] = {"camera_response": camera_data, "jpg_path": jpg_path}

    if save_path is None:
        references_dir = os.path.join(os.path.dirname(__file__), "..", "references")
        os.makedirs(references_dir, exist_ok=True)
        save_path = os.path.join(references_dir, "current_view.jpg")

    content = rc.fetch_image_bytes(jpg_path)
    with open(save_path, "wb") as f:
        f.write(content)
    result["saved_to"] = save_path
    return result


def cmd_close_robot() -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    state = rc.load_state()
    token = state.get("token", "") or ""

    if token:
        try:
            result["finalize_robot"] = rc.finalize_robot(token)
        except Exception as e:
            result["finalize_robot_error"] = str(e)

        try:
            result["consume_token"] = rc.consume_token(token)
        except Exception as e:
            result["consume_token_error"] = str(e)
    else:
        result["info"] = "本地状态中没有 token，跳过 finalize 和 consume。"

    result["state_reset"] = rc.reset_state_file()
    return result


def cmd_grip_open() -> Dict[str, Any]:
    return rc.grip_open(rc.ensure_ready())


def cmd_grip_close() -> Dict[str, Any]:
    return rc.grip_close(rc.ensure_ready())


def cmd_grip_position(value: int) -> Dict[str, Any]:
    return rc.grip_position(rc.ensure_ready(), value)


def cmd_perform(target: str, vel: int, acc: int, wait: int) -> Dict[str, Any]:
    return rc.perform(rc.ensure_ready(), target=target, vel=vel, acc=acc, wait=wait)


def cmd_safe(target: str) -> Dict[str, Any]:
    return rc.return_to_safe(rc.ensure_ready(), target=target)


def cmd_shutdown() -> Dict[str, Any]:
    token = rc.ensure_token_ready()
    result = rc.shutdown_robot(token)
    rc.save_state(token=token, initialized=False)
    return result


def cmd_status() -> Dict[str, Any]:
    return rc.load_state()


def cmd_agv_goto_location(location: str) -> Dict[str, Any]:
    return rc.agv_goto_location(rc.ensure_ready(), location)


def cmd_vehicle_stop() -> Dict[str, Any]:
    return rc.vehicle_stop(rc.ensure_ready())


def cmd_vehicle_home() -> Dict[str, Any]:
    return rc.vehicle_home(rc.ensure_ready())


def cmd_get_current_location() -> Dict[str, Any]:
    return rc.get_current_location(rc.ensure_ready())


# ===== 新增命令统一入口 =====
def run_namespaced_command(command: str, args: Dict[str, Any]) -> Dict[str, Any]:
    t = args.get("token")

    if command == "access_enum": return rc.access_enum(args.get("key"))
    if command == "sync_area": return rc.sync_area()

    if command == "authority_generate": return rc.authority_generate(args.get("robot", ""), args.get("mode", ""), args.get("serial", ""), maybe_int(args.get("forced") or 1) or 1)
    if command == "init_is_initialized": return rc.init_is_initialized()
    if command == "config_action_device_configurations": return rc.config_action_device_configurations()
    if command == "config_biosen_configurations": return rc.config_biosen_configurations()
    if command == "config_configurations": return rc.config_configurations(maybe_int(args.get("detail")))
    if command == "config_robot_configurations": return rc.config_robot_configurations(maybe_int(args.get("detail")))
    if command == "script_api_battery": return rc.script_api_battery()

    # token-only
    token_only = {
        "authority_consume": lambda: rc.authority_consume(resolve_token(t)),
        "authority_is_accessible": lambda: rc.authority_is_accessible(resolve_token(t)),
        "authority_is_controller": lambda: rc.authority_is_controller(resolve_token(t)),
        "authority_is_viewer": lambda: rc.authority_is_viewer(resolve_token(t)),
        "authority_loose": lambda: rc.authority_loose(resolve_token(t)),
        "authority_seize": lambda: rc.authority_seize(resolve_token(t), maybe_int(args.get("forced") or 0) or 0),
        "access_reset_robot": lambda: rc.access_reset_robot(resolve_token(t), maybe_int(args.get("recover") or 1) or 1, maybe_int(args.get("clear") or 1) or 1),
        "config_update_biosen_configurations": lambda: rc.config_update_biosen_configurations(resolve_token(t), args["equipment_id"], args["url"]),
        "config_update_configurations": lambda: rc.config_update_configurations(resolve_token(t), parse_json_arg(args.get("configurations"), "configurations")),
        "config_update_robot_configurations": lambda: rc.config_update_robot_configurations(resolve_token(t), parse_json_arg(args.get("configurations"), "configurations")),
        "script_api_clear_cur_location_offset": lambda: rc.script_api_clear_cur_location_offset(resolve_token(t)),
        "script_api_cur_location": lambda: rc.script_api_cur_location(resolve_token(t)),
        "script_api_cur_location_offset": lambda: rc.script_api_cur_location_offset(resolve_token(t)),
        "script_api_cur_lock": lambda: rc.script_api_cur_lock(resolve_token(t)),
        "script_api_get_consumable": lambda: rc.script_api_get_consumable(resolve_token(t), maybe_int(args.get("consumable")) or 0),
        "script_api_location_offset": lambda: rc.script_api_location_offset(resolve_token(t), args["area"]),
        "script_api_pose": lambda: rc.script_api_pose(resolve_token(t), args["area"], args["pose"]),
        "script_api_set_cur_location_offset": lambda: rc.script_api_set_cur_location_offset(resolve_token(t), args["location"], args["name"], parse_json_arg(args.get("location_offset"), "location_offset")),
        "script_delete": lambda: rc.script_delete(resolve_token(t), args["name"]),
        "script_exec": lambda: rc.script_exec(resolve_token(t), args["contents"], args.get("arguments")),
        "script_exec_by_name": lambda: rc.script_exec_by_name(resolve_token(t), args["name"], args.get("arguments")),
        "script_save": lambda: rc.script_save(resolve_token(t), args["name"], args["contents"]),
        "script_get": lambda: rc.script_get(resolve_token(t), args["name"]),
        "script_list": lambda: rc.script_list(resolve_token(t)),
        "script_status": lambda: rc.script_status(resolve_token(t)),
        "script_stop": lambda: rc.script_stop(resolve_token(t)),
        "init_initialize": lambda: rc.init_initialize(resolve_token(t), maybe_int(args.get("homed")), maybe_int(args.get("forced"))),
        "init_finalize": lambda: rc.init_finalize(resolve_token(t)),
    }
    if command.startswith("db_"):
        tok = resolve_token(t)
        a = args
        if command == "db_check_process": return rc.db_check_process(tok, a["area"])
        if command == "db_delete_area": return rc.db_delete_area(tok, a["delete_name"])
        if command == "db_delete_consumable": return rc.db_delete_consumable(tok, int(a["consumable_id"]))
        if command == "db_delete_link": return rc.db_delete_link(tok, a["link_name"])
        if command == "db_find_areas": return rc.db_find_areas(tok, a.get("name"), a.get("description"), maybe_int(a.get("rotation")))
        if command == "db_find_links_data": return rc.db_find_links_data(tok, a["area_name1"], a["area_name2"])
        if command == "db_get_all_link_pose": return rc.db_get_all_link_pose(tok)
        if command == "db_get_all_tag_area": return rc.db_get_all_tag_area(tok)
        if command == "db_get_area_pose": return rc.db_get_area_pose(tok, a["area_name"])
        if command == "db_get_areas_process": return rc.db_get_areas_process(tok, a["area_name"], a["process_type"])
        if command == "db_get_cache_area_pose": return rc.db_get_cache_area_pose(tok)
        if command == "db_get_consumable": return rc.db_get_consumable(tok)
        if command == "db_get_current_waypoint": return rc.db_get_current_waypoint(tok)
        if command == "db_get_eoats": return rc.db_get_eoats(tok)
        if command == "db_get_links_process": return rc.db_get_links_process(tok, a["link"])
        if command == "db_get_log_data": return rc.db_get_log_data(tok, a["start_date"], a["end_date"], a["level"])
        if command == "db_get_real_name_list": return rc.db_get_real_name_list(tok)
        if command == "db_get_waypoints": return rc.db_get_waypoints(tok, a["area_name"], a["pose"])
        if command == "db_new_area": return rc.db_new_area(tok, parse_json_arg(a.get("name_list"), "name_list"), a["eoat"], a["pose"], int(a["rotation"]), float(a["offset_z"]), a["type_value"], a["area_type"], a["tag_area"], float(a["upland_z"]), float(a["teach_plate_inside_z"]))
        if command == "db_save_consumable": return rc.db_save_consumable(tok, int(a["id"]), a["consumable_type"], a["name"], int(a["wells"]), float(a["offset_inside_z"]), float(a["offset_uncover_z"]), float(a["offset_lid_bottom"]), float(a["offset_covered"]), float(a["cover_squeexe"]), float(a["offset_bottom"]), float(a["squeeze"]), float(a["unsqueeze"]))
        if command == "db_save_new_link": return rc.db_save_new_link(tok, a["link_name"], a["area_from"], a["area_to"], a["pose_from"], a["pose_to"])
        if command == "db_save_waypoint": return rc.db_save_waypoint(tok, a["area_name"], a["pose"], parse_json_arg(a.get("waypoint"), "waypoint"))
        if command == "db_stack_continuation": return rc.db_stack_continuation(tok)
        if command == "db_update_area": return rc.db_update_area(tok, parse_json_arg(a.get("area_name_list"), "area_name_list"), a["edit_area_eoat"], a["area_forward"], float(a["area_offset_z"]))
        if command == "db_update_consumable": return rc.db_update_consumable(tok, int(a["id"]), a["consumable_type"], a["name"], int(a["wells"]), float(a["offset_inside_z"]), float(a["offset_uncover_z"]), float(a["offset_lid_bottom"]))
        if command == "db_update_link_process": return rc.db_update_link_process(tok, a["link"], parse_json_arg(a.get("process_list"), "process_list"))
        if command == "db_update_process": return rc.db_update_process(tok, a["area_name"], a["process_type"], parse_json_arg(a.get("process_list"), "process_list"))

    if command in token_only:
        return token_only[command]()

    # ready-required
    tok = resolve_token(t, require_ready=True)
    a = args
    if command == "action_agv_control_keep": return rc.action_agv_control_keep(tok)
    if command == "action_agv_control_motion": return rc.action_agv_control_motion(tok, float(a["vx"]), float(a["vy"]), float(a["vw"]))
    if command == "action_agv_control_stop": return rc.action_agv_control_stop(tok)
    if command == "action_agv_get_map_list": return rc.action_agv_get_map_list(tok)
    if command == "action_agv_goto_location": return rc.action_agv_goto_location(tok, a["location"])
    if command == "action_agv_load_map": return rc.action_agv_load_map(tok, a["map_name"])
    if command == "action_calibrate_location": return rc.action_calibrate_location(tok, a["area"])
    if command == "action_get_camera_jpg": return rc.action_get_camera_jpg(tok)
    if command == "action_get_camera_offset": return rc.action_get_camera_offset(tok)
    if command == "action_grip_control": return rc.action_grip_control(tok, a["action_type"], int(a["value"]))
    if command == "action_peripheral_control": return rc.action_peripheral_control(tok, a["peripheral"], a["action_type"], int(a["value"]))
    if command == "action_vehicle_home": return rc.action_vehicle_home(tok)
    if command == "action_vehicle_move": return rc.action_vehicle_move(tok, float(a["position"]), float(a["velocity"]))
    if command == "action_vehicle_reset": return rc.action_vehicle_reset(tok)
    if command == "action_vehicle_stop": return rc.action_vehicle_stop(tok)

    if command == "command_cover": return rc.command_cover(tok, a["store_lid_area"], a["cover_area"], int(a["consumable_id"]), int(a["wait"]))
    if command == "command_uncover": return rc.command_uncover(tok, a["uncover_area"], a["store_lid_area"], int(a["consumable_id"]), int(a["wait"]))
    if command == "command_perform": return rc.command_perform(tok, a["target"], maybe_int(a.get("consumable")), maybe_int(a.get("vel")), maybe_int(a.get("acc")), maybe_int(a.get("wait")))
    if command == "command_pick": return rc.command_pick(tok, a["target"], maybe_int(a.get("consumable")), maybe_int(a.get("vel")), maybe_int(a.get("acc")), maybe_int(a.get("wait")), maybe_int(a.get("covered")))
    if command == "command_place": return rc.command_place(tok, a["target"], maybe_int(a.get("consumable")), maybe_int(a.get("vel")), maybe_int(a.get("acc")), maybe_int(a.get("wait")), maybe_int(a.get("covered")))
    if command == "command_return_to_safe": return rc.command_return_to_safe(tok, a["target"])
    if command == "command_teach_array": return rc.command_teach_array(tok, a["area"], a["calc_type"], parse_json_arg(a.get("poses"), "poses"))
    if command == "command_transfer": return rc.command_transfer(tok, a["source"], a["target"], maybe_int(a.get("consumable")), maybe_int(a.get("vel")), maybe_int(a.get("acc")), maybe_int(a.get("wait")), maybe_int(a.get("covered")))

    if command == "robot_forward": return rc.robot_forward(tok, parse_json_arg(a.get("waypoint"), "waypoint"))
    if command == "robot_inverse": return rc.robot_inverse(tok, parse_json_arg(a.get("waypoint"), "waypoint"))
    if command == "robot_keep_joints_tuning_alive": return rc.robot_keep_joints_tuning_alive(tok)
    if command == "robot_keep_motion_alive": return rc.robot_keep_motion_alive(tok)
    if command == "robot_keep_pose_tuning_alive": return rc.robot_keep_pose_tuning_alive(tok)
    if command == "robot_move_camera_to_robot_offset": return rc.robot_move_camera_to_robot_offset(tok, float(a["vel"]), float(a["acc"]))
    if command == "robot_set_joints_stepping": return rc.robot_set_joints_stepping(tok, parse_json_arg(a.get("steps"), "steps"), float(a["velocity"]), float(a["acceleration"]))
    if command == "robot_set_joints_tuning": return rc.robot_set_joints_tuning(tok, parse_json_arg(a.get("directions"), "directions"), float(a["velocity"]), float(a["acceleration"]))
    if command == "robot_set_motion": return rc.robot_set_motion(tok, parse_json_arg(a.get("waypoint"), "waypoint"), a["motion"], float(a["vel"]), float(a["acc"]))
    if command == "robot_set_pose_stepping": return rc.robot_set_pose_stepping(tok, parse_json_arg(a.get("steps"), "steps"), float(a["velocity"]), float(a["acceleration"]))
    if command == "robot_set_pose_tuning": return rc.robot_set_pose_tuning(tok, parse_json_arg(a.get("directions"), "directions"), float(a["velocity"]), float(a["acceleration"]))
    if command == "robot_set_robot_coordinate_by_name": return rc.robot_set_robot_coordinate_by_name(tok, a["name"])
    if command == "robot_shutdown": return rc.robot_shutdown(tok)
    if command == "robot_stop_joints_tuning": return rc.robot_stop_joints_tuning(tok)
    if command == "robot_stop_motion": return rc.robot_stop_motion(tok)
    if command == "robot_stop_pose_tuning": return rc.robot_stop_pose_tuning(tok)

    if command == "script_api_align_location": return rc.script_api_align_location(tok, a["area"])
    if command == "script_api_calc_pose_base_location": return rc.script_api_calc_pose_base_location(tok, parse_json_arg(a.get("current_pos"), "current_pos"), parse_json_arg(a.get("base_pos"), "base_pos"), parse_json_arg(a.get("target_pos"), "target_pos"))
    if command == "script_api_calibrate_location": return rc.script_api_calibrate_location(tok, a["area"])
    if command == "script_api_current_pose": return rc.script_api_current_pose(tok, a["model"])
    if command == "script_api_forward": return rc.script_api_forward(tok, parse_json_arg(a.get("waypoint"), "waypoint"))
    if command == "script_api_grip_action": return rc.script_api_grip_action(tok, a["action_type"], int(a["value"]), maybe_int(a.get("grasp")), maybe_int(a.get("access")))
    if command == "script_api_inverse": return rc.script_api_inverse(tok, parse_json_arg(a.get("waypoint"), "waypoint"))
    if command == "script_api_move": return rc.script_api_move(tok, parse_json_arg(a.get("waypoint"), "waypoint"), a["motion"], float(a["vel"]), float(a["acc"]))
    if command == "script_api_move_to": return rc.script_api_move_to(tok, a["location"], float(a["vel"]), float(a["acc"]))
    if command == "script_api_peripheral_action": return rc.script_api_peripheral_action(tok, a["peripheral"], a["action_type"], int(a["value"]))
    if command == "script_api_reset_robot": return rc.script_api_reset_robot(tok, int(a["recover"]), int(a["clear"]))
    if command == "script_api_teach": return rc.script_api_teach(tok, parse_json_arg(a.get("pose"), "pose"))

    raise RobotApiError(f"未知命令: {command}")
