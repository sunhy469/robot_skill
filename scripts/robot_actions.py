from __future__ import annotations

import json
from pathlib import Path
from argparse import Namespace
from typing import Any, Dict, Optional

import robot_core as rc
from robot_core import RobotApiError
import requests


# =========================
# 通用参数处理
# =========================


def extract_result_value(response_data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    从接口返回中提取指定字段，兼容根层和 data 层两种结构。

    参数：
        response_data: 接口返回 JSON
        key: 字段名
        default: 默认值

    返回：
        Any: 提取到的字段值
    """
    if not isinstance(response_data, dict):
        return default

    if key in response_data:
        return response_data.get(key, default)

    data = response_data.get("data", {})
    if isinstance(data, dict) and key in data:
        return data.get(key, default)

    return default

def extract_camera_jpg_path(response_data: Dict[str, Any]) -> str:
    """
    从 get_camera_jpg 的返回结果中提取图片路径。

    参数：
        response_data: get_camera_jpg 的响应 JSON

    返回：
        str: 图片路径
    """
    data = response_data.get("data", {})
    if isinstance(data, dict) and data.get("jpg"):
        return str(data["jpg"])

    jpg_path = extract_result_value(response_data, "jpg", "")
    if jpg_path:
        return str(jpg_path)

    raise RobotApiError(f"相机返回结果中未找到 jpg 路径：{(response_data)}")

def join_url(base_url: str, path: str) -> str:
    """
    拼接完整接口地址。

    参数：
        base_url: 接口服务根地址
        path: 接口路径或完整 URL

    返回：
        str: 完整 URL
    """
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return base_url.rstrip("/") + "/" + path.lstrip("/")

def request_bytes(method: str, path: str) -> bytes:
    """
    发送请求并返回二进制数据，主要用于下载相机图片。

    参数：
        method: 请求方法
        path: 图片路径或完整 URL

    返回：
        bytes: 二进制内容
    """
    url = join_url("http://192.168.193.10:8300", path)

    try:
        response = requests.request(
            method=method.upper(),
            url=url,
            timeout=5.0
        )
    except requests.RequestException as e:
        raise RobotApiError(f"下载失败：{method} {url}，错误：{e}") from e

    if response.status_code != 200:
        raise RobotApiError(f"下载图片失败：HTTP {response.status_code}，内容：{response.text}")

    return response.content

def fetch_image_bytes(image_path: str) -> bytes:
    """
    根据图片路径下载图片二进制内容。

    参数：
        image_path: 图片路径或完整 URL

    返回：
        bytes: 图片二进制内容
    """
    return request_bytes("GET", image_path)


def _default_references_dir() -> Path:
    """返回 references 目录并确保存在。"""
    references_dir = Path(__file__).resolve().parent.parent / "references"
    references_dir.mkdir(parents=True, exist_ok=True)
    return references_dir


def save_image_bytes(content: bytes, save_path: Optional[str] = None, default_name: str = "current_view.jpg") -> str:
    """
    将图片字节内容保存到本地文件，默认写入 references 目录。
    """
    if save_path is None:
        target_path = _default_references_dir() / default_name
    else:
        target_path = Path(save_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

    with open(target_path, "wb") as f:
        f.write(content)
    return str(target_path.resolve())


def calculate_image_similarity(path_a: str, path_b: str) -> float:
    """
    使用 Pillow 计算两张图的像素相似度（0~1）。
    """
    try:
        from PIL import Image, ImageOps
    except Exception as e:
        raise RobotApiError("未安装 Pillow，无法进行图像相似度比对，请先安装: pip install pillow") from e

    with Image.open(path_a) as img_a, Image.open(path_b) as img_b:
        gray_a = ImageOps.grayscale(img_a)
        gray_b = ImageOps.grayscale(img_b).resize(gray_a.size)

        pixels_a = list(gray_a.getdata())
        pixels_b = list(gray_b.getdata())
        if not pixels_a:
            return 0.0

        # 平均绝对差 -> 相似度
        mad = sum(abs(int(pa) - int(pb)) for pa, pb in zip(pixels_a, pixels_b)) / len(pixels_a)
        similarity = max(0.0, min(1.0, 1.0 - mad / 255.0))
        return similarity


def detect_consumable_by_reference(
    true_view_path: str,
    current_view_path: str,
    similarity_threshold: float = 0.97,
) -> Dict[str, Any]:
    """
    基于参考图判断板位是否有耗材：
    当前图与 true_view 一致或足够相似，判定为有耗材。
    """
    if not Path(true_view_path).exists():
        raise RobotApiError(f"参考图片不存在：{true_view_path}")
    if not Path(current_view_path).exists():
        raise RobotApiError(f"当前图片不存在：{current_view_path}")

    similarity = calculate_image_similarity(true_view_path, current_view_path)
    has_consumable = similarity >= similarity_threshold
    return {
        "has_consumable": has_consumable,
        "similarity": similarity,
        "threshold": similarity_threshold,
        "true_view_path": str(Path(true_view_path).resolve()),
        "current_view_path": str(Path(current_view_path).resolve()),
    }

def parse_json_arg(text: Optional[str], arg_name: str) -> Any:
    """将 CLI 的 JSON 字符串参数解析为 Python 对象。"""
    if text is None:
        return None
    try:
        return json.loads(text)
    except Exception as e:
        raise RobotApiError(f"参数 {arg_name} JSON 解析失败: {e}") from e


def parse_int_arg(text: Optional[str], arg_name: str, default: Optional[int] = None) -> int:
    """将 CLI 参数安全解析为 int，支持默认值。"""
    if text is None:
        if default is None:
            raise RobotApiError(f"参数 {arg_name} 不能为空")
        return default
    try:
        return int(text)
    except Exception as e:
        raise RobotApiError(f"参数 {arg_name} 需为整数，当前值={text!r}") from e



def drop_none_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """过滤值为 None 的可选字段。"""
    return {k: v for k, v in data.items() if v is not None}


def resolve_token(token: Optional[str] = None, require_ready: bool = False, require_initialized: bool = False) -> str:
    """解析 token：优先显式 token，否则从状态文件与保障逻辑中获取。"""
    if token:
        return token
    if require_ready or require_initialized:
        return rc.ensure_initialized()
    return rc.ensure_token_ready()


def _tok(args: Namespace, ready: bool = False) -> str:
    return resolve_token(getattr(args, "token", None), require_ready=ready)



def cmd_init_all() -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    token_resp = rc.authority_generate(forced=1)
    token = str(rc.extract_result_value(token_resp, "token", "") or "")
    result["generate_token"] = token_resp

    try:
        result["vehicle_reset"] = rc.action_vehicle_reset(token)
    except Exception as e:
        result["vehicle_reset_error"] = str(e)

    try:
        result["reset_robot"] = rc.access_reset_robot(token, recover=1, clear=1)
    except Exception as e:
        result["reset_robot_error"] = str(e)

    result["initialize_robot"] = rc.init_initialize(token, homed=1, forced=0)
    result["state"] = rc.save_state(token=token, initialized=True)
    return result

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
    return rc.action_agv_control_motion(_tok(args, ready=True), args.vx,args.vy, args.vw)


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
    camera_data = rc.action_get_camera_jpg(_tok(args, ready=True))
    jpg_path = extract_camera_jpg_path(camera_data)
    result = {
        "camera_response": camera_data,
        "jpg_path": jpg_path
    }
    content = fetch_image_bytes(jpg_path)
    result["saved_to"] = save_image_bytes(content, default_name="current_view.jpg")

    return result


def cmd_action_detect_consumable(args: Namespace) -> Dict[str, Any]:
    """
    执行 perform 后抓拍当前视图，并与 references/true_view 对比判断是否有耗材。
    """
    token = _tok(args, ready=True)
    perform_result = rc.command_perform(token, "移动到拍摄位置")

    camera_data = rc.action_get_camera_jpg(_tok(args, ready=True))
    jpg_path = extract_camera_jpg_path(camera_data)
    content = fetch_image_bytes(jpg_path)
    saved_current = save_image_bytes(content, default_name="current_view.jpg")

    true_view = str(_default_references_dir() / "true_view.jpg")
    compare_result = detect_consumable_by_reference(
        true_view_path=true_view,
        current_view_path=saved_current,
        similarity_threshold=0.97,
    )
    return {
        "perform_result": perform_result,
        "camera_response": camera_data,
        "jpg_path": jpg_path,
        "saved_current_view": saved_current,
        "compare_result": compare_result,
    }


def cmd_action_get_camera_offset(args: Namespace) -> Dict[str, Any]:
    """获取相机偏移。"""
    return rc.action_get_camera_offset(_tok(args, ready=True))


def cmd_action_grip_control(args: Namespace) -> Dict[str, Any]:
    """控制夹爪动作。"""
    return rc.action_grip_control(_tok(args, ready=True), args.action_type, args.value)


def cmd_action_peripheral_control(args: Namespace) -> Dict[str, Any]:
    """控制外围设备动作。"""
    return rc.action_peripheral_control(_tok(args, ready=True), args.peripheral, args.action_type, args.value)


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
    return rc.command_cover(_tok(args, ready=True), args.store_lid_area, args.cover_area, args.consumable_id, args.wait)


def cmd_command_uncover(args: Namespace) -> Dict[str, Any]:
    """执行揭盖动作。"""
    return rc.command_uncover(_tok(args, ready=True), args.uncover_area, args.store_lid_area,args.consumable_id,args.wait)


def cmd_command_perform(args: Namespace) -> Dict[str, Any]:
    """执行区域动作。"""
    return rc.command_perform(_tok(args, ready=True), args.target, args.vel, args.acc, args.wait)


def cmd_command_pick(args: Namespace) -> Dict[str, Any]:
    """执行取样动作。"""
    return rc.command_pick(_tok(args, ready=True), args.target, args.consumable, args.vel, args.acc, args.wait, args.covered)


def cmd_command_place(args: Namespace) -> Dict[str, Any]:
    """执行放样动作。"""
    return rc.command_place(_tok(args, ready=True), args.target, args.consumable, args.vel, args.acc, args.wait, args.covered)


def cmd_command_return_to_safe(args: Namespace) -> Dict[str, Any]:
    """机器人回安全位。"""
    return rc.command_return_to_safe(_tok(args, ready=True), args.target)


def cmd_command_teach_array(args: Namespace) -> Dict[str, Any]:
    """示教阵列位姿。"""
    return rc.command_teach_array(_tok(args, ready=True), args.area, args.calc_type, parse_json_arg(args.poses, "poses"))


def cmd_command_transfer(args: Namespace) -> Dict[str, Any]:
    """执行转移动作。"""
    return rc.command_transfer(_tok(args, ready=True), args.source, args.target, args.consumable, args.vel, args.acc, args.wait, args.covered)


# configuration

def cmd_config_action_device_configurations(args: Namespace) -> Dict[str, Any]:
    """读取动作设备配置。"""
    return rc.config_action_device_configurations()


def cmd_config_biosen_configurations(args: Namespace) -> Dict[str, Any]:
    """读取 biosen 配置。"""
    return rc.config_biosen_configurations()


def cmd_config_configurations(args: Namespace) -> Dict[str, Any]:
    """读取机器人配置。"""
    return rc.config_configurations(parse_int_arg(args.detail, "detail", default=0))


def cmd_config_robot_configurations(args: Namespace) -> Dict[str, Any]:
    """读取上装机械臂配置。"""
    return rc.config_robot_configurations(parse_int_arg(args.detail, "detail", default=0))


def cmd_config_update_biosen_configurations(args: Namespace) -> Dict[str, Any]:
    """更新 biosen 配置。"""
    return rc.config_update_biosen_configurations(_tok(args), args.equipment_id, args.url)


def cmd_config_update_configurations(args: Namespace) -> Dict[str, Any]:
    """更新机器人配置。暂不支持"""
    return rc.config_update_configurations(_tok(args), parse_json_arg(args.configurations, "configurations"))


def cmd_config_update_robot_configurations(args: Namespace) -> Dict[str, Any]:
    """更新上装机械臂配置。暂不支持"""
    return rc.config_update_robot_configurations(_tok(args), parse_json_arg(args.configurations, "configurations"))


# database

def cmd_db_check_process(args: Namespace) -> Dict[str, Any]: return rc.db_check_process(_tok(args), args.area)
def cmd_db_delete_area(args: Namespace) -> Dict[str, Any]: return rc.db_delete_area(_tok(args), args.delete_name)
def cmd_db_delete_consumable(args: Namespace) -> Dict[str, Any]: return rc.db_delete_consumable(_tok(args), args.consumable_id)
def cmd_db_delete_link(args: Namespace) -> Dict[str, Any]: return rc.db_delete_link(_tok(args), args.link_name)
def cmd_db_find_areas(args: Namespace) -> Dict[str, Any]: return rc.db_find_areas(_tok(args), args.name, args.description, args.rotation)
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
def cmd_db_save_consumable(args: Namespace) -> Dict[str, Any]: return rc.db_save_consumable(_tok(args), args.id, args.consumable_type, args.name, args.wells, args.offset_inside_z, args.offset_uncover_z, args.offset_lid_bottom, args.offset_covered,args.cover_squeexe, args.offset_bottom,args.squeeze, args.unsqueeze)
def cmd_db_save_new_link(args: Namespace) -> Dict[str, Any]: return rc.db_save_new_link(_tok(args), args.link_name, args.area_from, args.area_to, args.pose_from, args.pose_to)
def cmd_db_save_waypoint(args: Namespace) -> Dict[str, Any]: return rc.db_save_waypoint(_tok(args), args.area_name, args.pose,args.waypoint)
def cmd_db_stack_continuation(args: Namespace) -> Dict[str, Any]: return rc.db_stack_continuation(_tok(args))
def cmd_db_update_area(args: Namespace) -> Dict[str, Any]: return rc.db_update_area(_tok(args), args.area_name_list, args.edit_area_eoat, args.area_forward, args.area_offset_z)
def cmd_db_update_consumable(args: Namespace) -> Dict[str, Any]: return rc.db_update_consumable(_tok(args), args.id, args.consumable_type, args.name, args.wells, args.offset_inside_z, args.offset_uncover_z, args.offset_lid_bottom)
def cmd_db_update_link_process(args: Namespace) -> Dict[str, Any]: return rc.db_update_link_process(_tok(args), args.link, args.process_list)
def cmd_db_update_process(args: Namespace) -> Dict[str, Any]: return rc.db_update_process(_tok(args), args.area_name, args.process_type, args.process_list)


# init

def cmd_init_is_initialized(args: Namespace) -> Dict[str, Any]:
    """查询初始化状态。"""
    return rc.init_is_initialized()


def cmd_init_initialize(args: Namespace) -> Dict[str, Any]:
    """执行初始化流程。"""
    return rc.init_initialize(
        _tok(args),
        parse_int_arg(args.homed, "homed", default=1),
        parse_int_arg(args.forced, "forced", default=0),
    )


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
def cmd_script_api_grip_action(args: Namespace) -> Dict[str, Any]:
    return rc.script_api_grip_action(
        _tok(args, ready=True),
        args.action_type,
        parse_int_arg(args.value, "value"),
        parse_int_arg(args.grasp, "grasp", default=0),
        parse_int_arg(args.access, "access", default=0),
    )
def cmd_script_api_inverse(args: Namespace) -> Dict[str, Any]: return rc.script_api_inverse(_tok(args, ready=True), parse_json_arg(args.waypoint, "waypoint"))
def cmd_script_api_location_offset(args: Namespace) -> Dict[str, Any]: return rc.script_api_location_offset(_tok(args), args.area)
def cmd_script_api_move(args: Namespace) -> Dict[str, Any]: return rc.script_api_move(_tok(args, ready=True), parse_json_arg(args.waypoint, "waypoint"), args.motion, float(args.vel), float(args.acc))
def cmd_script_api_move_to(args: Namespace) -> Dict[str, Any]: return rc.script_api_move_to(_tok(args, ready=True), args.location, float(args.vel), float(args.acc))
def cmd_script_api_peripheral_action(args: Namespace) -> Dict[str, Any]: return rc.script_api_peripheral_action(_tok(args, ready=True), args.peripheral, args.action_type, args.value)
def cmd_script_api_pose(args: Namespace) -> Dict[str, Any]: return rc.script_api_pose(_tok(args), args.area, args.pose)
def cmd_script_api_reset_robot(args: Namespace) -> Dict[str, Any]: return rc.script_api_reset_robot(_tok(args, ready=True), int(args.recover), int(args.clear))
def cmd_script_api_set_cur_location_offset(args: Namespace) -> Dict[str, Any]: return rc.script_api_set_cur_location_offset(_tok(args), args.location, args.name, parse_json_arg(args.location_offset, "location_offset"))
def cmd_script_api_teach(args: Namespace) -> Dict[str, Any]: return rc.script_api_teach(_tok(args, ready=True), args.pose)


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
