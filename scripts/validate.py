
"""OpenClaw 机器人 Skill CLI 入口（兼容壳）。"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any, Callable, Dict

import robot_actions
from robot_actions import (
    cmd_init_all,
)
from robot_core import RobotApiError


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s - %(message)s",
        stream=sys.stderr,
    )


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _add_token(p: argparse.ArgumentParser) -> None:
    p.add_argument("--token", default=None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="validate.py", description="汇像机器人控制脚本，供 OpenClaw Skill 调用")
    sub = parser.add_subparsers(dest="command", required=True)

    # compatibility command
    sub.add_parser("init_all", help="执行完整初始化流程")

    # new commands (all namespaced)
    p = sub.add_parser("access_enum"); p.add_argument("--key")
    p = sub.add_parser("access_reset_robot"); _add_token(p); p.add_argument("--recover", default=1); p.add_argument("--clear", default=1)

    for name in ["action_agv_control_keep", "action_agv_control_stop", "action_agv_get_map_list", "action_get_camera_offset", "action_vehicle_home", "action_vehicle_reset", "action_vehicle_stop"]:
        p = sub.add_parser(name); _add_token(p)

    p = sub.add_parser("action_get_camera_jpg"); _add_token(p)
    p = sub.add_parser("action_detect_consumable"); _add_token(p)

    p = sub.add_parser("action_agv_control_motion"); _add_token(p); 
    p.add_argument('--vx', type=str, default='30.0', help='X轴速度，字符串类型')
    p.add_argument('--vy', type=str, default='30.0', help='Y轴速度，字符串类型')
    p.add_argument('--vw', type=str, default='20.0', help='角速度，字符串类型')

    p = sub.add_parser("action_agv_goto_location"); _add_token(p); p.add_argument("--location", required=True)
    p = sub.add_parser("action_agv_load_map"); _add_token(p); p.add_argument("--map_name", required=True)
    p = sub.add_parser("action_agv_translate")
    p.add_argument("--dist", required=True, type=str, help="直线运动距离，单位 m")
    p.add_argument("--vx", type=str, default="0.05", help="X 方向速度，单位 m/s（默认 0.05）")
    p.add_argument("--vy", type=str, default="0.0", help="Y 方向速度，单位 m/s（默认 0.0）")
    p.add_argument("--mode", type=str, default="0", help="0=里程模式，1=定位模式（默认 0）")
    p.add_argument("--ip", default="192.168.193.5", type=str, help="AGV TCP IP")
    p.add_argument("--port", default="19206", type=str, help="AGV TCP 端口")
    p = sub.add_parser("action_agv_turn")
    p.add_argument("--angle", required=True, type=str, help="转动角度，单位 rad，绝对值，可大于 2π")
    p.add_argument("--vw", required=True, type=str, help="角速度，单位 rad/s，正值逆时针，负值顺时针")
    p.add_argument("--mode", type=str, default="0", help="0=里程模式，1=定位模式（默认 0）")
    p.add_argument("--ip", default="192.168.193.5", type=str, help="AGV TCP IP")
    p.add_argument("--port", default="19206", type=str, help="AGV TCP 端口")
    p = sub.add_parser("action_calibrate_location"); _add_token(p); p.add_argument("--area", required=True)
    p = sub.add_parser("action_grip_control"); _add_token(p); p.add_argument("--action_type", required=True); p.add_argument("--value", type=str, required=False)
    p = sub.add_parser("action_peripheral_control"); _add_token(p); p.add_argument("--peripheral", required=True); p.add_argument("--action_type", required=True); p.add_argument("--value", type=str, required=True)
    p = sub.add_parser("action_vehicle_move"); _add_token(p); p.add_argument("--position", type=str,  required=True); p.add_argument("--velocity",  type=str, required=True)

    p = sub.add_parser("authority_generate"); p.add_argument("--robot", default=""); p.add_argument("--mode", default=""); p.add_argument("--serial", default=""); p.add_argument("--forced", default=1)
    for name in ["authority_consume", "authority_is_accessible", "authority_is_controller", "authority_is_viewer", "authority_loose"]:
        p = sub.add_parser(name); _add_token(p)
    p = sub.add_parser("authority_seize"); _add_token(p); p.add_argument("--forced", default=0)

    p = sub.add_parser("command_cover"); _add_token(p); p.add_argument("--store_lid_area", required=True); p.add_argument("--cover_area", required=True); p.add_argument("--consumable_id", required=True); p.add_argument("--wait", required=True)
    p = sub.add_parser("command_uncover"); _add_token(p); p.add_argument("--uncover_area", required=True); p.add_argument("--store_lid_area", required=True); p.add_argument("--consumable_id", required=True); p.add_argument("--wait", required=True)
    for name in ["command_perform", "command_pick", "command_place"]:
        p = sub.add_parser(name); _add_token(p); p.add_argument("--target", required=True); p.add_argument("--consumable"); p.add_argument("--vel"); p.add_argument("--acc"); p.add_argument("--wait"); p.add_argument("--covered")
    p = sub.add_parser("command_return_to_safe"); _add_token(p); p.add_argument("--target", required=True)
    p = sub.add_parser("command_teach_array"); _add_token(p); p.add_argument("--area", required=True); p.add_argument("--calc_type", required=True); p.add_argument("--poses", required=True)
    p = sub.add_parser("command_transfer"); _add_token(p); p.add_argument("--source", required=True); p.add_argument("--target", required=True); p.add_argument("--consumable"); p.add_argument("--vel"); p.add_argument("--acc"); p.add_argument("--wait"); p.add_argument("--covered")

    for name in ["config_action_device_configurations", "config_biosen_configurations"]:
        sub.add_parser(name)
    p = sub.add_parser("config_configurations"); p.add_argument("--detail")
    p = sub.add_parser("config_robot_configurations"); p.add_argument("--detail")
    p = sub.add_parser("config_update_biosen_configurations"); _add_token(p); p.add_argument("--equipment_id", required=True); p.add_argument("--url", required=True)
    p = sub.add_parser("config_update_configurations"); _add_token(p); p.add_argument("--configurations", required=True)
    p = sub.add_parser("config_update_robot_configurations"); _add_token(p); p.add_argument("--configurations", required=True)

    db_args = {
        "db_check_process": ["area"], "db_delete_area": ["delete_name"], "db_delete_consumable": ["consumable_id"], "db_delete_link": ["link_name"],
        "db_find_areas": ["name", "description", "rotation"], "db_find_links_data": ["area_name1", "area_name2"], "db_get_area_pose": ["area_name"],
        "db_get_areas_process": ["area_name", "process_type"], "db_get_links_process": ["link"], "db_get_log_data": ["start_date", "end_date", "level"],
        "db_get_waypoints": ["area_name", "pose"],
        "db_new_area": ["name_list", "eoat", "pose", "rotation", "offset_z", "type", "area_type", "tag_area", "upland_z", "teach_plate_inside_z"],
        "db_save_consumable": ["id", "consumable_type", "name", "wells", "offset_inside_z", "offset_uncover_z", "offset_lid_bottom", "offset_covered", "cover_squeexe", "offset_bottom", "squeeze", "unsqueeze"],
        "db_save_new_link": ["link_name", "area_from", "area_to", "pose_from", "pose_to"], "db_save_waypoint": ["area_name", "pose", "waypoint"],
        "db_update_area": ["area_name_list", "edit_area_eoat", "area_forward", "area_offset_z"], "db_update_consumable": ["id", "consumable_type", "name", "wells", "offset_inside_z", "offset_uncover_z", "offset_lid_bottom"],
        "db_update_link_process": ["link", "process_list"], "db_update_process": ["area_name", "process_type", "process_list"],
    }
    for name in ["db_get_all_link_pose", "db_get_all_tag_area", "db_get_cache_area_pose", "db_get_consumable", "db_get_current_waypoint", "db_get_eoats", "db_get_real_name_list", "db_stack_continuation"]:
        p = sub.add_parser(name); _add_token(p)
    for name, fields in db_args.items():
        p = sub.add_parser(name); _add_token(p)
        for f in fields:
            p.add_argument(f"--{f}")

    p = sub.add_parser("init_is_initialized")
    p = sub.add_parser("init_initialize"); _add_token(p); p.add_argument("--homed"); p.add_argument("--forced")
    p = sub.add_parser("init_finalize"); _add_token(p)

    robot = {
        "robot_forward": ["waypoint"], "robot_inverse": ["waypoint"], "robot_move_camera_to_robot_offset": ["vel", "acc"],
        "robot_set_joints_stepping": ["steps", "velocity", "acceleration"], "robot_set_joints_tuning": ["directions", "velocity", "acceleration"],
        "robot_set_motion": ["waypoint", "motion", "vel", "acc"], "robot_set_pose_stepping": ["steps", "velocity", "acceleration"],
        "robot_set_pose_tuning": ["directions", "velocity", "acceleration"], "robot_set_robot_coordinate_by_name": ["name"],
    }
    for name in ["robot_keep_joints_tuning_alive", "robot_keep_motion_alive", "robot_keep_pose_tuning_alive", "robot_shutdown", "robot_stop_joints_tuning", "robot_stop_motion", "robot_stop_pose_tuning"]:
        p = sub.add_parser(name); _add_token(p)
    for name, fields in robot.items():
        p = sub.add_parser(name); _add_token(p)
        for f in fields: p.add_argument(f"--{f}", required=True)

    sapis = {
        "script_api_align_location": ["area"], "script_api_calc_pose_base_location": ["current_pos", "base_pos", "target_pos"],
        "script_api_calibrate_location": ["area"], "script_api_current_pose": ["model"], "script_api_forward": ["waypoint"],
        "script_api_get_consumable": ["consumable"], "script_api_grip_action": ["action_type", "value", "grasp", "access"],
        "script_api_inverse": ["waypoint"], "script_api_location_offset": ["area"], "script_api_move": ["waypoint", "motion", "vel", "acc"],
        "script_api_move_to": ["location", "vel", "acc"], "script_api_peripheral_action": ["peripheral", "action_type", "value"],
        "script_api_pose": ["area", "pose"], "script_api_reset_robot": ["recover", "clear"], "script_api_set_cur_location_offset": ["location", "name", "location_offset"],
        "script_api_teach": ["pose"],
    }
    sub.add_parser("script_api_battery")
    for name in ["script_api_clear_cur_location_offset", "script_api_cur_location", "script_api_cur_location_offset", "script_api_cur_lock"]:
        p = sub.add_parser(name); _add_token(p)
    for name, fields in sapis.items():
        p = sub.add_parser(name); _add_token(p)
        for f in fields:
            p.add_argument(f"--{f}", required=f not in {"grasp", "access"})

    p = sub.add_parser("script_delete"); _add_token(p); p.add_argument("--name", required=True)
    p = sub.add_parser("script_exec"); _add_token(p); p.add_argument("--contents", required=True); p.add_argument("--arguments")
    p = sub.add_parser("script_exec_by_name"); _add_token(p); p.add_argument("--name", required=True); p.add_argument("--arguments")
    p = sub.add_parser("script_save"); _add_token(p); p.add_argument("--name", required=True); p.add_argument("--contents", required=True)
    p = sub.add_parser("script_get"); _add_token(p); p.add_argument("--name", required=True)
    for name in ["script_list", "script_status", "script_stop", "sync_area"]:
        p = sub.add_parser(name)
        if name != "sync_area": _add_token(p)

    return parser


def main() -> int:
    _setup_logging()
    parser = build_parser()
    args = parser.parse_args()

    command_handlers: Dict[str, Callable[[], Dict[str, Any]]] = {
        "init_all": cmd_init_all,
    }

    try:
        if args.command in command_handlers:
            result = command_handlers[args.command]()
        else:
            handler_name = f"cmd_{args.command}"
            if not hasattr(robot_actions, handler_name):
                raise RobotApiError(f"未知命令：{args.command}")
            result = getattr(robot_actions, handler_name)(args)

        print(_json_dumps({"success": True, "command": args.command, "result": result}))
        return 0
    except RobotApiError as e:
        print(_json_dumps({"success": False, "error": str(e)}))
        return 2
    except Exception as e:
        print(_json_dumps({"success": False, "error": f"未预期异常：{e}"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
