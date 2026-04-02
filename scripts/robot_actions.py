from __future__ import annotations

import json
import os
from argparse import Namespace
from typing import Any, Dict, Optional

import robot_core as rc
from robot_core import RobotApiError


# =========================
# 通用参数处理
# =========================

def parse_json_arg(text: Optional[str], arg_name: str) -> Any:
    """将 CLI 的 JSON 字符串参数解析为 Python 对象。"""
    if text is None:
        return None
    try:
        return json.loads(text)
    except Exception as e:
        raise RobotApiError(f"参数 {arg_name} JSON 解析失败: {e}") from e


def maybe_int(value: Any) -> Optional[int]:
    """可选整数转换。"""
    if value is None:
        return None
    return int(value)


def maybe_float(value: Any) -> Optional[float]:
    """可选浮点转换。"""
    if value is None:
        return None
    return float(value)


def require_int(value: Any, arg_name: str) -> int:
    """必填整数转换。"""
    if value is None:
        raise RobotApiError(f"参数 {arg_name} 不能为空")
    try:
        return int(value)
    except Exception as e:
        raise RobotApiError(f"参数 {arg_name} 必须是整数: {value}") from e


def require_float(value: Any, arg_name: str) -> float:
    """必填浮点转换。"""
    if value is None:
        raise RobotApiError(f"参数 {arg_name} 不能为空")
    try:
        return float(value)
    except Exception as e:
        raise RobotApiError(f"参数 {arg_name} 必须是数字: {value}") from e


def drop_none_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """过滤值为 None 的可选字段。"""
    return {k: v for k, v in data.items() if v is not None}


def resolve_token(token: Optional[str] = None, require_ready: bool = False, require_initialized: bool = False) -> str:
    """解析 token：优先显式 token，否则从状态文件与保障逻辑中获取。"""
    if token:
        return token
    if require_ready or require_initialized:
        return rc.ensure_ready()
    return rc.ensure_token_ready()


def _tok(args: Namespace, ready: bool = False) -> str:
    return resolve_token(getattr(args, "token", None), require_ready=ready)


# =========================
# 旧命令：保持兼容
# =========================

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


def cmd_camera(args: Namespace) -> Dict[str, Any]:
    """获取相机图片并保存到本地。"""
    token = rc.ensure_ready()
    camera_data = rc.get_camera_jpg(token)
    jpg_path = rc.extract_camera_jpg_path(camera_data)

    result: Dict[str, Any] = {"camera_response": camera_data, "jpg_path": jpg_path}

    save_path = args.out
    if save_path is None:
        references_dir = os.path.join(os.path.dirname(__file__), "..", "references")
        os.makedirs(references_dir, exist_ok=True)
        save_path = os.path.join(references_dir, "current_view.jpg")

    content = rc.fetch_image_bytes(jpg_path)
    with open(save_path, "wb") as f:
        f.write(content)
    result["saved_to"] = save_path
    return result


def cmd_close_robot(args: Namespace) -> Dict[str, Any]:
    """关闭机器人并重置本地状态。"""
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


def cmd_grip_open(args: Namespace) -> Dict[str, Any]:
    """打开夹爪。"""
    return rc.grip_open(rc.ensure_ready())


def cmd_grip_close(args: Namespace) -> Dict[str, Any]:
    """关闭夹爪。"""
    return rc.grip_close(rc.ensure_ready())


def cmd_grip_position(args: Namespace) -> Dict[str, Any]:
    """夹爪移动到指定位置。"""
    return rc.grip_position(rc.ensure_ready(), args.value)


def cmd_perform(args: Namespace) -> Dict[str, Any]:
    """执行区域动作。"""
    return rc.perform(rc.ensure_ready(), target=args.target, vel=args.vel, acc=args.acc, wait=args.wait)


def cmd_safe(args: Namespace) -> Dict[str, Any]:
    """回到安全位。"""
    return rc.return_to_safe(rc.ensure_ready(), target=args.target)

def cmd_shutdown(args: Namespace) -> Dict[str, Any]:
    """执行机器人急停。"""
    token = rc.ensure_token_ready()
    result = rc.shutdown_robot(token)
    rc.save_state(token=token, initialized=False)
    return result


def cmd_status(args: Namespace) -> Dict[str, Any]:
    """查看本地状态。"""
    return rc.load_state()


def cmd_agv_goto(args: Namespace) -> Dict[str, Any]:
    """控制 AGV 前往指定站点。"""
    return rc.agv_goto_location(rc.ensure_ready(), args.location)


def cmd_vehicle_stop(args: Namespace) -> Dict[str, Any]:
    """停止移动工具。"""
    return rc.vehicle_stop(rc.ensure_ready())


def cmd_vehicle_home(args: Namespace) -> Dict[str, Any]:
    """移动工具回零。"""
    return rc.vehicle_home(rc.ensure_ready())


def cmd_vehicle_location(args: Namespace) -> Dict[str, Any]:
    """获取当前移动工具位置。"""
    return rc.get_current_location(rc.ensure_ready())


# =========================
# 新命令：每个能力一个 def
# =========================

# access

def cmd_access_enum(args: Namespace) -> Dict[str, Any]:
    """查询 access 枚举能力。"""
    return rc.access_enum(args.key)


def cmd_access_reset_robot(args: Namespace) -> Dict[str, Any]:
    """执行访问层复位能力。"""
    return rc.access_reset_robot(_tok(args), int(args.recover), int(args.clear))


# actionControl

def cmd_action_agv_control_keep(args: Namespace) -> Dict[str, Any]:
    """保持 AGV 控制活跃。"""
    return rc.action_agv_control_keep(_tok(args, ready=True))


def cmd_action_agv_control_motion(args: Namespace) -> Dict[str, Any]:
    """下发 AGV 速度控制指令。"""
    return rc.action_agv_control_motion(_tok(args, ready=True), float(args.vx), float(args.vy), float(args.vw))


def cmd_action_agv_control_stop(args: Namespace) -> Dict[str, Any]:
    """停止 AGV 速度控制。"""
    return rc.action_agv_control_stop(_tok(args, ready=True))


def cmd_action_agv_get_map_list(args: Namespace) -> Dict[str, Any]:
    """查询 AGV 地图列表。"""
    return rc.action_agv_get_map_list(_tok(args, ready=True))


def cmd_action_agv_goto_location(args: Namespace) -> Dict[str, Any]:
    """控制 AGV 前往指定站点。"""
    return rc.action_agv_goto_location(_tok(args, ready=True), args.location)


def cmd_action_agv_load_map(args: Namespace) -> Dict[str, Any]:
    """加载指定 AGV 地图。"""
    return rc.action_agv_load_map(_tok(args, ready=True), args.map_name)


def cmd_action_calibrate_location(args: Namespace) -> Dict[str, Any]:
    """执行站点标定。"""
    return rc.action_calibrate_location(_tok(args, ready=True), args.area)


def cmd_action_get_camera_jpg(args: Namespace) -> Dict[str, Any]:
    """获取相机抓拍信息。"""
    return rc.action_get_camera_jpg(_tok(args, ready=True))


def cmd_action_get_camera_offset(args: Namespace) -> Dict[str, Any]:
    """获取相机偏移。"""
    return rc.action_get_camera_offset(_tok(args, ready=True))


def cmd_action_grip_control(args: Namespace) -> Dict[str, Any]:
    """控制夹爪动作。"""
    return rc.action_grip_control(_tok(args, ready=True), args.action_type, int(args.value))


def cmd_action_peripheral_control(args: Namespace) -> Dict[str, Any]:
    """控制外围设备动作。"""
    return rc.action_peripheral_control(_tok(args, ready=True), args.peripheral, args.action_type, int(args.value))


def cmd_action_vehicle_home(args: Namespace) -> Dict[str, Any]:
    """车辆回零。"""
    return rc.action_vehicle_home(_tok(args, ready=True))


def cmd_action_vehicle_move(args: Namespace) -> Dict[str, Any]:
    """车辆定点移动。"""
    return rc.action_vehicle_move(_tok(args, ready=True), float(args.position), float(args.velocity))


def cmd_action_vehicle_reset(args: Namespace) -> Dict[str, Any]:
    """车辆复位。"""
    return rc.action_vehicle_reset(_tok(args, ready=True))


def cmd_action_vehicle_stop(args: Namespace) -> Dict[str, Any]:
    """车辆停止。"""
    return rc.action_vehicle_stop(_tok(args, ready=True))


# authority

def cmd_authority_generate(args: Namespace) -> Dict[str, Any]:
    """申请控制 token。"""
    return rc.authority_generate(args.robot, args.mode, args.serial, int(args.forced))


def cmd_authority_consume(args: Namespace) -> Dict[str, Any]:
    """释放控制 token。"""
    return rc.authority_consume(_tok(args))


def cmd_authority_is_accessible(args: Namespace) -> Dict[str, Any]:
    """检查 token 是否可访问。"""
    return rc.authority_is_accessible(_tok(args))


def cmd_authority_is_controller(args: Namespace) -> Dict[str, Any]:
    """检查是否控制者。"""
    return rc.authority_is_controller(_tok(args))


def cmd_authority_is_viewer(args: Namespace) -> Dict[str, Any]:
    """检查是否观察者。"""
    return rc.authority_is_viewer(_tok(args))


def cmd_authority_loose(args: Namespace) -> Dict[str, Any]:
    """主动放弃控制权。"""
    return rc.authority_loose(_tok(args))


def cmd_authority_seize(args: Namespace) -> Dict[str, Any]:
    """抢占控制权。"""
    return rc.authority_seize(_tok(args), int(args.forced))


# command

def cmd_command_cover(args: Namespace) -> Dict[str, Any]:
    """执行盖盖动作。"""
    return rc.command_cover(_tok(args, ready=True), args.store_lid_area, args.cover_area, int(args.consumable_id), int(args.wait))


def cmd_command_uncover(args: Namespace) -> Dict[str, Any]:
    """执行揭盖动作。"""
    return rc.command_uncover(_tok(args, ready=True), args.uncover_area, args.store_lid_area, int(args.consumable_id), int(args.wait))


def cmd_command_perform(args: Namespace) -> Dict[str, Any]:
    """执行区域动作。"""
    return rc.command_perform(_tok(args, ready=True), args.target, maybe_int(args.consumable), maybe_int(args.vel), maybe_int(args.acc), maybe_int(args.wait))


def cmd_command_pick(args: Namespace) -> Dict[str, Any]:
    """执行取样动作。"""
    return rc.command_pick(_tok(args, ready=True), args.target, maybe_int(args.consumable), maybe_int(args.vel), maybe_int(args.acc), maybe_int(args.wait), maybe_int(args.covered))


def cmd_command_place(args: Namespace) -> Dict[str, Any]:
    """执行放样动作。"""
    return rc.command_place(_tok(args, ready=True), args.target, maybe_int(args.consumable), maybe_int(args.vel), maybe_int(args.acc), maybe_int(args.wait), maybe_int(args.covered))


def cmd_command_return_to_safe(args: Namespace) -> Dict[str, Any]:
    """机器人回安全位。"""
    return rc.command_return_to_safe(_tok(args, ready=True), args.target)


def cmd_command_teach_array(args: Namespace) -> Dict[str, Any]:
    """示教阵列位姿。"""
    return rc.command_teach_array(_tok(args, ready=True), args.area, args.calc_type, parse_json_arg(args.poses, "poses"))


def cmd_command_transfer(args: Namespace) -> Dict[str, Any]:
    """执行转移动作。"""
    return rc.command_transfer(_tok(args, ready=True), args.source, args.target, maybe_int(args.consumable), maybe_int(args.vel), maybe_int(args.acc), maybe_int(args.wait), maybe_int(args.covered))


# configuration

def cmd_config_action_device_configurations(args: Namespace) -> Dict[str, Any]:
    """读取动作设备配置。"""
    return rc.config_action_device_configurations()


def cmd_config_biosen_configurations(args: Namespace) -> Dict[str, Any]:
    """读取 biosen 配置。"""
    return rc.config_biosen_configurations()


def cmd_config_configurations(args: Namespace) -> Dict[str, Any]:
    """读取系统配置。"""
    return rc.config_configurations(maybe_int(args.detail))


def cmd_config_robot_configurations(args: Namespace) -> Dict[str, Any]:
    """读取机器人配置。"""
    return rc.config_robot_configurations(maybe_int(args.detail))


def cmd_config_update_biosen_configurations(args: Namespace) -> Dict[str, Any]:
    """更新 biosen 配置。"""
    return rc.config_update_biosen_configurations(_tok(args), args.equipment_id, args.url)


def cmd_config_update_configurations(args: Namespace) -> Dict[str, Any]:
    """更新系统配置。"""
    return rc.config_update_configurations(_tok(args), parse_json_arg(args.configurations, "configurations"))


def cmd_config_update_robot_configurations(args: Namespace) -> Dict[str, Any]:
    """更新机器人配置。"""
    return rc.config_update_robot_configurations(_tok(args), parse_json_arg(args.configurations, "configurations"))


# database

def cmd_db_check_process(args: Namespace) -> Dict[str, Any]: return rc.db_check_process(_tok(args), args.area)
def cmd_db_delete_area(args: Namespace) -> Dict[str, Any]: return rc.db_delete_area(_tok(args), args.delete_name)
def cmd_db_delete_consumable(args: Namespace) -> Dict[str, Any]: return rc.db_delete_consumable(_tok(args), require_int(args.consumable_id, "consumable_id"))
def cmd_db_delete_link(args: Namespace) -> Dict[str, Any]: return rc.db_delete_link(_tok(args), args.link_name)
def cmd_db_find_areas(args: Namespace) -> Dict[str, Any]: return rc.db_find_areas(_tok(args), args.name, args.description, maybe_int(args.rotation))
def cmd_db_find_links_data(args: Namespace) -> Dict[str, Any]: return rc.db_find_links_data(_tok(args), args.area_name1, args.area_name2)
def cmd_db_get_all_link_pose(args: Namespace) -> Dict[str, Any]: return rc.db_get_all_link_pose(_tok(args))
def cmd_db_get_all_tag_area(args: Namespace) -> Dict[str, Any]: return rc.db_get_all_tag_area(_tok(args))
def cmd_db_get_area_pose(args: Namespace) -> Dict[str, Any]: return rc.db_get_area_pose(_tok(args), args.area_name)
def cmd_db_get_areas_process(args: Namespace) -> Dict[str, Any]: return rc.db_get_areas_process(_tok(args), args.area_name, args.process_type)
def cmd_db_get_cache_area_pose(args: Namespace) -> Dict[str, Any]: return rc.db_get_cache_area_pose(_tok(args))
def cmd_db_get_consumable(args: Namespace) -> Dict[str, Any]: return rc.db_get_consumable(_tok(args))
def cmd_db_get_current_waypoint(args: Namespace) -> Dict[str, Any]: return rc.db_get_current_waypoint(_tok(args))
def cmd_db_get_eoats(args: Namespace) -> Dict[str, Any]: return rc.db_get_eoats(_tok(args))
def cmd_db_get_links_process(args: Namespace) -> Dict[str, Any]: return rc.db_get_links_process(_tok(args), args.link)
def cmd_db_get_log_data(args: Namespace) -> Dict[str, Any]: return rc.db_get_log_data(_tok(args), args.start_date, args.end_date, args.level)
def cmd_db_get_real_name_list(args: Namespace) -> Dict[str, Any]: return rc.db_get_real_name_list(_tok(args))
def cmd_db_get_waypoints(args: Namespace) -> Dict[str, Any]: return rc.db_get_waypoints(_tok(args), args.area_name, args.pose)
def cmd_db_new_area(args: Namespace) -> Dict[str, Any]: return rc.db_new_area(_tok(args), parse_json_arg(args.name_list, "name_list"), args.eoat, args.pose, require_int(args.rotation, "rotation"), require_float(args.offset_z, "offset_z"), args.type_value, args.area_type, args.tag_area, require_float(args.upland_z, "upland_z"), require_float(args.teach_plate_inside_z, "teach_plate_inside_z"))
def cmd_db_save_consumable(args: Namespace) -> Dict[str, Any]: return rc.db_save_consumable(_tok(args), require_int(args.id, "id"), args.consumable_type, args.name, require_int(args.wells, "wells"), require_float(args.offset_inside_z, "offset_inside_z"), require_float(args.offset_uncover_z, "offset_uncover_z"), require_float(args.offset_lid_bottom, "offset_lid_bottom"), require_float(args.offset_covered, "offset_covered"), require_float(args.cover_squeexe, "cover_squeexe"), require_float(args.offset_bottom, "offset_bottom"), require_float(args.squeeze, "squeeze"), require_float(args.unsqueeze, "unsqueeze"))
def cmd_db_save_new_link(args: Namespace) -> Dict[str, Any]: return rc.db_save_new_link(_tok(args), args.link_name, args.area_from, args.area_to, args.pose_from, args.pose_to)
def cmd_db_save_waypoint(args: Namespace) -> Dict[str, Any]: return rc.db_save_waypoint(_tok(args), args.area_name, args.pose, parse_json_arg(args.waypoint, "waypoint"))
def cmd_db_stack_continuation(args: Namespace) -> Dict[str, Any]: return rc.db_stack_continuation(_tok(args))
def cmd_db_update_area(args: Namespace) -> Dict[str, Any]: return rc.db_update_area(_tok(args), parse_json_arg(args.area_name_list, "area_name_list"), args.edit_area_eoat, args.area_forward, require_float(args.area_offset_z, "area_offset_z"))
def cmd_db_update_consumable(args: Namespace) -> Dict[str, Any]: return rc.db_update_consumable(_tok(args), require_int(args.id, "id"), args.consumable_type, args.name, require_int(args.wells, "wells"), require_float(args.offset_inside_z, "offset_inside_z"), require_float(args.offset_uncover_z, "offset_uncover_z"), require_float(args.offset_lid_bottom, "offset_lid_bottom"))
def cmd_db_update_link_process(args: Namespace) -> Dict[str, Any]: return rc.db_update_link_process(_tok(args), args.link, parse_json_arg(args.process_list, "process_list"))
def cmd_db_update_process(args: Namespace) -> Dict[str, Any]: return rc.db_update_process(_tok(args), args.area_name, args.process_type, parse_json_arg(args.process_list, "process_list"))


# init

def cmd_init_is_initialized(args: Namespace) -> Dict[str, Any]:
    """查询初始化状态。"""
    return rc.init_is_initialized()


def cmd_init_initialize(args: Namespace) -> Dict[str, Any]:
    """执行初始化流程。"""
    return rc.init_initialize(_tok(args), maybe_int(args.homed), maybe_int(args.forced))


def cmd_init_finalize(args: Namespace) -> Dict[str, Any]:
    """执行反初始化流程。"""
    return rc.init_finalize(_tok(args))


# robotControl

def cmd_robot_forward(args: Namespace) -> Dict[str, Any]: return rc.robot_forward(_tok(args, ready=True), parse_json_arg(args.waypoint, "waypoint"))
def cmd_robot_inverse(args: Namespace) -> Dict[str, Any]: return rc.robot_inverse(_tok(args, ready=True), parse_json_arg(args.waypoint, "waypoint"))
def cmd_robot_keep_joints_tuning_alive(args: Namespace) -> Dict[str, Any]: return rc.robot_keep_joints_tuning_alive(_tok(args, ready=True))
def cmd_robot_keep_motion_alive(args: Namespace) -> Dict[str, Any]: return rc.robot_keep_motion_alive(_tok(args, ready=True))
def cmd_robot_keep_pose_tuning_alive(args: Namespace) -> Dict[str, Any]: return rc.robot_keep_pose_tuning_alive(_tok(args, ready=True))
def cmd_robot_move_camera_to_robot_offset(args: Namespace) -> Dict[str, Any]: return rc.robot_move_camera_to_robot_offset(_tok(args, ready=True), float(args.vel), float(args.acc))
def cmd_robot_set_joints_stepping(args: Namespace) -> Dict[str, Any]: return rc.robot_set_joints_stepping(_tok(args, ready=True), parse_json_arg(args.steps, "steps"), float(args.velocity), float(args.acceleration))
def cmd_robot_set_joints_tuning(args: Namespace) -> Dict[str, Any]: return rc.robot_set_joints_tuning(_tok(args, ready=True), parse_json_arg(args.directions, "directions"), float(args.velocity), float(args.acceleration))
def cmd_robot_set_motion(args: Namespace) -> Dict[str, Any]: return rc.robot_set_motion(_tok(args, ready=True), parse_json_arg(args.waypoint, "waypoint"), args.motion, float(args.vel), float(args.acc))
def cmd_robot_set_pose_stepping(args: Namespace) -> Dict[str, Any]: return rc.robot_set_pose_stepping(_tok(args, ready=True), parse_json_arg(args.steps, "steps"), float(args.velocity), float(args.acceleration))
def cmd_robot_set_pose_tuning(args: Namespace) -> Dict[str, Any]: return rc.robot_set_pose_tuning(_tok(args, ready=True), parse_json_arg(args.directions, "directions"), float(args.velocity), float(args.acceleration))
def cmd_robot_set_robot_coordinate_by_name(args: Namespace) -> Dict[str, Any]: return rc.robot_set_robot_coordinate_by_name(_tok(args, ready=True), args.name)
def cmd_robot_shutdown(args: Namespace) -> Dict[str, Any]: return rc.robot_shutdown(_tok(args, ready=True))
def cmd_robot_stop_joints_tuning(args: Namespace) -> Dict[str, Any]: return rc.robot_stop_joints_tuning(_tok(args, ready=True))
def cmd_robot_stop_motion(args: Namespace) -> Dict[str, Any]: return rc.robot_stop_motion(_tok(args, ready=True))
def cmd_robot_stop_pose_tuning(args: Namespace) -> Dict[str, Any]: return rc.robot_stop_pose_tuning(_tok(args, ready=True))


# script-api

def cmd_script_api_align_location(args: Namespace) -> Dict[str, Any]: return rc.script_api_align_location(_tok(args, ready=True), args.area)
def cmd_script_api_battery(args: Namespace) -> Dict[str, Any]: return rc.script_api_battery()
def cmd_script_api_calc_pose_base_location(args: Namespace) -> Dict[str, Any]: return rc.script_api_calc_pose_base_location(_tok(args, ready=True), parse_json_arg(args.current_pos, "current_pos"), parse_json_arg(args.base_pos, "base_pos"), parse_json_arg(args.target_pos, "target_pos"))
def cmd_script_api_calibrate_location(args: Namespace) -> Dict[str, Any]: return rc.script_api_calibrate_location(_tok(args, ready=True), args.area)
def cmd_script_api_clear_cur_location_offset(args: Namespace) -> Dict[str, Any]: return rc.script_api_clear_cur_location_offset(_tok(args))
def cmd_script_api_cur_location(args: Namespace) -> Dict[str, Any]: return rc.script_api_cur_location(_tok(args))
def cmd_script_api_cur_location_offset(args: Namespace) -> Dict[str, Any]: return rc.script_api_cur_location_offset(_tok(args))
def cmd_script_api_cur_lock(args: Namespace) -> Dict[str, Any]: return rc.script_api_cur_lock(_tok(args))
def cmd_script_api_current_pose(args: Namespace) -> Dict[str, Any]: return rc.script_api_current_pose(_tok(args, ready=True), args.model)
def cmd_script_api_forward(args: Namespace) -> Dict[str, Any]: return rc.script_api_forward(_tok(args, ready=True), parse_json_arg(args.waypoint, "waypoint"))
def cmd_script_api_get_consumable(args: Namespace) -> Dict[str, Any]: return rc.script_api_get_consumable(_tok(args), int(args.consumable))
def cmd_script_api_grip_action(args: Namespace) -> Dict[str, Any]: return rc.script_api_grip_action(_tok(args, ready=True), args.action_type, int(args.value), maybe_int(args.grasp), maybe_int(args.access))
def cmd_script_api_inverse(args: Namespace) -> Dict[str, Any]: return rc.script_api_inverse(_tok(args, ready=True), parse_json_arg(args.waypoint, "waypoint"))
def cmd_script_api_location_offset(args: Namespace) -> Dict[str, Any]: return rc.script_api_location_offset(_tok(args), args.area)
def cmd_script_api_move(args: Namespace) -> Dict[str, Any]: return rc.script_api_move(_tok(args, ready=True), parse_json_arg(args.waypoint, "waypoint"), args.motion, float(args.vel), float(args.acc))
def cmd_script_api_move_to(args: Namespace) -> Dict[str, Any]: return rc.script_api_move_to(_tok(args, ready=True), args.location, float(args.vel), float(args.acc))
def cmd_script_api_peripheral_action(args: Namespace) -> Dict[str, Any]: return rc.script_api_peripheral_action(_tok(args, ready=True), args.peripheral, args.action_type, int(args.value))
def cmd_script_api_pose(args: Namespace) -> Dict[str, Any]: return rc.script_api_pose(_tok(args), args.area, args.pose)
def cmd_script_api_reset_robot(args: Namespace) -> Dict[str, Any]: return rc.script_api_reset_robot(_tok(args, ready=True), int(args.recover), int(args.clear))
def cmd_script_api_set_cur_location_offset(args: Namespace) -> Dict[str, Any]: return rc.script_api_set_cur_location_offset(_tok(args), args.location, args.name, parse_json_arg(args.location_offset, "location_offset"))
def cmd_script_api_teach(args: Namespace) -> Dict[str, Any]: return rc.script_api_teach(_tok(args, ready=True), parse_json_arg(args.pose, "pose"))


# script

def cmd_script_delete(args: Namespace) -> Dict[str, Any]: return rc.script_delete(_tok(args), args.name)
def cmd_script_exec(args: Namespace) -> Dict[str, Any]: return rc.script_exec(_tok(args), args.contents, args.arguments)
def cmd_script_exec_by_name(args: Namespace) -> Dict[str, Any]: return rc.script_exec_by_name(_tok(args), args.name, args.arguments)
def cmd_script_save(args: Namespace) -> Dict[str, Any]: return rc.script_save(_tok(args), args.name, args.contents)
def cmd_script_get(args: Namespace) -> Dict[str, Any]: return rc.script_get(_tok(args), args.name)
def cmd_script_list(args: Namespace) -> Dict[str, Any]: return rc.script_list(_tok(args))
def cmd_script_status(args: Namespace) -> Dict[str, Any]: return rc.script_status(_tok(args))
def cmd_script_stop(args: Namespace) -> Dict[str, Any]: return rc.script_stop(_tok(args))


# sync

def cmd_sync_area(args: Namespace) -> Dict[str, Any]:
    """同步区域信息。"""
    return rc.sync_area()
