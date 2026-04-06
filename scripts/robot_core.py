from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Optional

import requests

# =========================
# 配置与常量
# =========================

BASE_URL = "http://192.168.193.10:8300"
API_TIMEOUT = 5.0
STATE_FILE = os.path.join(os.path.dirname(__file__), "robot_state.json")

logger = logging.getLogger("robot_core")


# =========================
# 异常定义
# =========================

class RobotApiError(RuntimeError):
    """机器人接口调用异常。"""


class RobotNetworkError(RobotApiError):
    """网络层异常。"""


class RobotHttpError(RobotApiError):
    """HTTP 状态码异常。"""


class RobotBusinessError(RobotApiError):
    """接口业务失败。"""


class RobotStateError(RobotApiError):
    """本地状态异常。"""


# =========================
# 通用工具
# =========================

def json_dumps(data: Any) -> str:
    """将对象格式化为 JSON 字符串。"""
    try:
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception:
        return str(data)


def now_ts() -> int:
    """秒级时间戳。"""
    return int(time.time())


def join_url(base_url: str, path: str) -> str:
    """拼接完整 URL。"""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def extract_result_value(response_data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """兼容根层 / data 层提取字段。"""
    if not isinstance(response_data, dict):
        return default
    if key in response_data:
        return response_data.get(key, default)
    data = response_data.get("data", {})
    if isinstance(data, dict) and key in data:
        return data.get(key, default)
    return default


# =========================
# 状态存储
# =========================

def default_state() -> Dict[str, Any]:
    return {"token": "", "initialized": False, "last_update": 0}


def load_state() -> Dict[str, Any]:
    if not os.path.exists(STATE_FILE):
        return default_state()
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        state = default_state()
        state.update(data if isinstance(data, dict) else {})
        return state
    except Exception as e:
        logger.warning("load_state failed, fallback default: %s", e)
        return default_state()


def save_state(token: Optional[str] = None, initialized: Optional[bool] = None) -> Dict[str, Any]:
    state = load_state()
    if token is not None:
        state["token"] = token
    if initialized is not None:
        state["initialized"] = initialized
    state["last_update"] = now_ts()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    return state


def reset_state_file() -> Dict[str, Any]:
    state = {"token": "", "initialized": False, "last_update": now_ts()}
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    return state


# =========================
# HTTP 请求与响应处理
# =========================

def request_json(method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = join_url(BASE_URL, path)
    req = payload or {}
    logger.info("request_json %s %s", method.upper(), url)
    try:
        resp = requests.request(method=method.upper(), url=url, json=req, timeout=API_TIMEOUT)
    except requests.RequestException as e:
        raise RobotNetworkError(f"请求失败：{method} {url}，错误：{e}") from e

    if resp.status_code != 200:
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        raise RobotHttpError(f"接口返回异常：HTTP {resp.status_code}，内容：{json_dumps(detail)}")

    try:
        data = resp.json()
    except Exception as e:
        raise RobotHttpError(f"响应不是合法 JSON：{resp.text}") from e

    if isinstance(data, dict) and data.get("success") is False:
        raise RobotBusinessError(f"接口业务返回失败：{json_dumps(data)}")
    return data


def request_bytes(method: str, path: str) -> bytes:
    url = join_url(BASE_URL, path)
    logger.info("request_bytes %s %s", method.upper(), url)
    try:
        resp = requests.request(method=method.upper(), url=url, timeout=API_TIMEOUT)
    except requests.RequestException as e:
        raise RobotNetworkError(f"下载失败：{method} {url}，错误：{e}") from e
    if resp.status_code != 200:
        raise RobotHttpError(f"下载图片失败：HTTP {resp.status_code}，内容：{resp.text}")
    return resp.content


def require_token(token: str) -> None:
    if not token:
        raise RobotStateError("当前没有 token，请先初始化机器人。")


def with_token(token: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    require_token(token)
    data = payload or {}
    data["token"] = token
    return data


# =========================
# token / 初始化保障逻辑
# =========================

def ensure_token_ready() -> str:
    state = load_state()
    token = state.get("token", "") or ""

    if not token:
        logger.info("ensure_token_ready: no local token, generating")
        data = authority_generate(forced=1)
        new_token = extract_result_value(data, "token", "")
        if not new_token:
            raise RobotStateError(f"generate_token 未返回 token：{json_dumps(data)}")
        save_state(token=new_token)
        return str(new_token)

    try:
        accessible = str(extract_result_value(authority_is_accessible(token), "result", 0)) == "1"
        controller = str(extract_result_value(authority_is_controller(token), "result", 0)) == "1"
        if accessible and controller:
            logger.info("ensure_token_ready: reuse local token")
            return token
        logger.warning("ensure_token_ready: local token invalid, regenerating")
    except Exception as e:
        logger.warning("ensure_token_ready: token check failed: %s", e)

    data = authority_generate(forced=1)
    new_token = extract_result_value(data, "token", "")
    if not new_token:
        raise RobotStateError(f"generate_token 未返回 token：{json_dumps(data)}")
    save_state(token=str(new_token))
    return str(new_token)


def ensure_initialized() -> str:
    token = ensure_token_ready()
    init_state = init_is_initialized()
    raw_status = extract_result_value(init_state, "status", 0)
    try:
        status = int(raw_status)
    except Exception:
        status = 0

    if status == 2:
        save_state(token=token, initialized=True)
        return token

    logger.info("ensure_initialized: current status=%s, begin initialization", status)
    try:
        action_vehicle_reset(token)
    except Exception as e:
        logger.warning("vehicle_reset failed (degraded): %s", e)
    try:
        access_reset_robot(token, recover=1, clear=1)
    except Exception as e:
        logger.warning("reset_robot failed (degraded): %s", e)

    init_initialize(token, homed=1, forced=1)
    save_state(token=token, initialized=True)
    return token


def _drop_none_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in payload.items() if v is not None}


# --- access ---
def access_enum(key: Optional[str] = None) -> Dict[str, Any]:
    """POST /access/enum/"""
    return request_json("POST", "/access/enum/", _drop_none_fields({"key": key}))


def access_reset_robot(token: str, recover: int = 1, clear: int = 1) -> Dict[str, Any]:
    """POST /access/resetRobot/"""
    return request_json("POST", "/access/resetRobot/", with_token(token, {"recover": int(recover), "clear": int(clear)}))


# --- actionControl ---
def action_agv_control_keep(token: str) -> Dict[str, Any]:
    """POST /actionControl/agvControlKeep/"""
    return request_json("POST", "/actionControl/agvControlKeep/", with_token(token, {}))


def action_agv_control_motion(token: str, vx: float, vy: str, vw: str) -> Dict[str, Any]:
    """POST /actionControl/agvControlMotion/"""
    return request_json("POST", "/actionControl/agvControlMotion/", with_token(token, {"vx": vx, "vy": vy, "vw": vw}))


def action_agv_control_stop(token: str) -> Dict[str, Any]:
    """POST /actionControl/agvControlStop/"""
    return request_json("POST", "/actionControl/agvControlStop/", with_token(token, {}))


def action_agv_get_map_list(token: str) -> Dict[str, Any]:
    """POST /actionControl/agvGetMapList/"""
    return request_json("POST", "/actionControl/agvGetMapList/", with_token(token, {}))


def action_agv_goto_location(token: str, location: str) -> Dict[str, Any]:
    """POST /actionControl/agvGotoLocation/"""
    return request_json("POST", "/actionControl/agvGotoLocation/", with_token(token, {"location": location}))


def action_agv_load_map(token: str, map_name: str) -> Dict[str, Any]:
    """POST /actionControl/agvLoadMap/"""
    return request_json("POST", "/actionControl/agvLoadMap/", with_token(token, {"mapName": map_name}))


def action_calibrate_location(token: str, area: str) -> Dict[str, Any]:
    """POST /actionControl/calibrateLocation/"""
    return request_json("POST", "/actionControl/calibrateLocation/", with_token(token, {"area": area}))


def action_get_camera_jpg(token: str) -> Dict[str, Any]:
    """POST /actionControl/getCameraJpg/"""
    return request_json("POST", "/actionControl/getCameraJpg/", with_token(token, {}))


def action_get_camera_offset(token: str) -> Dict[str, Any]:
    """POST /actionControl/getCameraOffset/"""
    return request_json("POST", "/actionControl/getCameraOffset/", with_token(token, {}))


def action_grip_control(token: str, action_type: str, value: Optional[str] = None) -> Dict[str, Any]:
    """POST /actionControl/gripControl/"""
    return request_json("POST", "/actionControl/gripControl/", with_token(token, _drop_none_fields({"actionType": action_type, "value": value})))


def action_peripheral_control(token: str, peripheral: str, action_type: str, value: str) -> Dict[str, Any]:
    """POST /actionControl/peripheralControl/"""
    return request_json(
        "POST",
        "/actionControl/peripheralControl/",
        with_token(token, {"peripheral": peripheral, "actionType": action_type, "value": value}),
    )


def action_vehicle_home(token: str) -> Dict[str, Any]:
    """POST /actionControl/vehicleHome/"""
    return request_json("POST", "/actionControl/vehicleHome/", with_token(token, {}))


def action_vehicle_move(token: str, position: float, velocity: str) -> Dict[str, Any]:
    """POST /actionControl/vehicleMove/"""
    return request_json("POST", "/actionControl/vehicleMove/", with_token(token, {"position": position, "velocity": velocity}))


def action_vehicle_reset(token: str) -> Dict[str, Any]:
    """POST /actionControl/vehicleReset/"""
    return request_json("POST", "/actionControl/vehicleReset/", with_token(token, {}))


def action_vehicle_stop(token: str) -> Dict[str, Any]:
    """POST /actionControl/vehicleStop/"""
    return request_json("POST", "/actionControl/vehicleStop/", with_token(token, {}))


# --- authority ---
def authority_consume(token: str) -> Dict[str, Any]:
    """POST /authority/consume/"""
    return request_json("POST", "/authority/consume/", with_token(token, {}))


def authority_generate(robot: str = "", mode: str = "", serial: str = "", forced: int = 1) -> Dict[str, Any]:
    """POST /authority/generate/"""
    return request_json("POST", "/authority/generate/", {"robot": robot, "mode": mode, "serial": serial, "forced": int(forced)})


def authority_is_accessible(token: str) -> Dict[str, Any]:
    """POST /authority/isAccessible/"""
    return request_json("POST", "/authority/isAccessible/", with_token(token, {}))


def authority_is_controller(token: str) -> Dict[str, Any]:
    """POST /authority/isController/"""
    return request_json("POST", "/authority/isController/", with_token(token, {}))


def authority_is_viewer(token: str) -> Dict[str, Any]:
    """POST /authority/isViewer/"""
    return request_json("POST", "/authority/isViewer/", with_token(token, {}))


def authority_loose(token: str) -> Dict[str, Any]:
    """POST /authority/loose/"""
    return request_json("POST", "/authority/loose/", with_token(token, {}))


def authority_seize(token: str, forced: int = 1) -> Dict[str, Any]:
    """POST /authority/seize/"""
    return request_json("POST", "/authority/seize/", with_token(token, {"forced": int(forced)}))


# --- command ---
def command_cover(token: str, store_lid_area: str, cover_area: str, consumable_id: str, wait: str = 0) -> Dict[str, Any]:
    return request_json("POST", "/command/cover/", with_token(token, {"storeLidArea": store_lid_area, "coverArea": cover_area, "consumableId": consumable_id, "wait": wait}))


def command_uncover(token: str, uncover_area: str, store_lid_area: str, consumable_id: str, wait: str = 0) -> Dict[str, Any]:
    return request_json("POST", "/command/uncover/", with_token(token, {"uncoverArea": uncover_area, "storeLidArea": store_lid_area, "consumableId": consumable_id, "wait": wait}))


def command_perform(token: str, target: str, vel: Optional[str] = 30, acc: Optional[str] = 30, wait: Optional[str] = 0) -> Dict[str, Any]:
    payload = _drop_none_fields({"target": target, "vel": vel, "acc": acc, "wait": wait})

    wait_int = 0
    if wait is not None:
        try:
            wait_int = int(wait)
        except (TypeError, ValueError):
            wait_int = 1

    if wait_int == 0:
        # 异步模式：发送即返回，不等待响应
        logger.info("perform (async): sending command to %s without waiting", target)
        try:
            request_json("POST", "/command/perform/", with_token(token, payload))
            return {"success": True, "mode": "async", "message": f"指令已发送到 {target}，机器人正在执行"}
        except RobotNetworkError as e:
            # 即使是网络错误，也可能是因为发送成功了只是没收到响应
            logger.warning("perform (async): network error but command may have been sent: %s", e)
            return {"success": True, "mode": "async", "message": f"指令可能已发送到 {target}（网络响应超时），建议稍后查看状态确认"}
    else:
        # 同步模式：等待结果
        logger.info("perform (sync): executing %s and waiting for completion", target)
        return request_json("POST", "/command/perform/", with_token(token, payload))
    


def command_pick(token: str, target: str, consumable: Optional[str] = None, vel: Optional[str] = None, acc: Optional[str] = None, wait: Optional[str] = 0, covered: Optional[str] = None) -> Dict[str, Any]:
    return request_json("POST", "/command/pick/", with_token(token, _drop_none_fields({"target": target, "consumable": consumable, "vel": vel, "acc": acc, "wait": wait, "covered": covered})))


def command_place(token: str, target: str, consumable: Optional[str] = None, vel: Optional[str] = None, acc: Optional[str] = None, wait: Optional[str] = 0, covered: Optional[str] = None) -> Dict[str, Any]:
    return request_json("POST", "/command/place/", with_token(token, _drop_none_fields({"target": target, "consumable": consumable, "vel": vel, "acc": acc, "wait": wait, "covered": covered})))


def command_return_to_safe(token: str, target: str) -> Dict[str, Any]:
    return request_json("POST", "/command/returnToSafe/", with_token(token, {"target": target}))


def command_teach_array(token: str, area: str, calc_type: str, poses: Any) -> Dict[str, Any]:
    return request_json("POST", "/command/teachArray/", with_token(token, {"area": area, "calcType": calc_type, "poses": poses}))


def command_transfer(token: str, source: str, target: str, consumable: Optional[str] = None, vel: Optional[str] = None, acc: Optional[str] = None, wait: Optional[str] = 0, covered: Optional[str] = None) -> Dict[str, Any]:
    return request_json("POST", "/command/transfer/", with_token(token, _drop_none_fields({"source": source, "target": target, "consumable": consumable, "vel": vel, "acc": acc, "wait": wait, "covered": covered})))


# --- configuration ---
def config_action_device_configurations() -> Dict[str, Any]:
    return request_json("POST", "/configuration/actionDeviceConfigurations/", {})


def config_biosen_configurations() -> Dict[str, Any]:
    return request_json("POST", "/configuration/biosenConfigurations/", {})


def config_configurations(detail: Optional[int] = None) -> Dict[str, Any]:
    return request_json("POST", "/configuration/configurations/", _drop_none_fields({"detail": detail}))


def config_robot_configurations(detail: Optional[int] = None) -> Dict[str, Any]:
    return request_json("POST", "/configuration/robotConfigurations/", _drop_none_fields({"detail": detail}))


def config_update_biosen_configurations(token: str, equipment_id: str, url: str) -> Dict[str, Any]:
    return request_json("POST", "/configuration/updateBiosenConfigurations/", with_token(token, {"equipmentId": equipment_id, "url": url}))


def config_update_configurations(token: str, configurations: Any) -> Dict[str, Any]:
    return request_json("POST", "/configuration/updateConfigurations/", with_token(token, {"configurations": configurations}))


def config_update_robot_configurations(token: str, configurations: Any) -> Dict[str, Any]:
    return request_json("POST", "/configuration/updateRobotConfigurations/", with_token(token, {"configurations": configurations}))


# --- database ---
def db_check_process(token: str, area: str) -> Dict[str, Any]: return request_json("POST", "/database/checkProcess/", with_token(token, {"area": area}))
def db_delete_area(token: str, delete_name: str) -> Dict[str, Any]: return request_json("POST", "/database/deleteArea/", with_token(token, {"deleteName": delete_name}))
def db_delete_consumable(token: str, consumable_id: str) -> Dict[str, Any]: return request_json("POST", "/database/deleteConsumable/", with_token(token, {"id": consumable_id}))
def db_delete_link(token: str, link_name: str) -> Dict[str, Any]: return request_json("POST", "/database/deleteLink/", with_token(token, {"linkNmae": link_name}))
def db_find_areas(token: str, name: Optional[str] = None, description: Optional[str] = None, rotation: Optional[str] = None) -> Dict[str, Any]: return request_json("POST", "/database/findAreas/", with_token(token, _drop_none_fields({"name": name, "description": description, "rotation": rotation})))
def db_find_links_data(token: str, area_name1: str, area_name2: str) -> Dict[str, Any]: return request_json("POST", "/database/findLinksData/", with_token(token, {"areaName1": area_name1, "areaName2": area_name2}))
def db_get_all_link_pose(token: str) -> Dict[str, Any]: return request_json("POST", "/database/getAllLinkPose/", with_token(token, {}))
def db_get_all_tag_area(token: str) -> Dict[str, Any]: return request_json("POST", "/database/getAllTagArea/", with_token(token, {}))
def db_get_area_pose(token: str, area_name: str) -> Dict[str, Any]: return request_json("POST", "/database/getAreaPose/", with_token(token, {"areaName": area_name}))
def db_get_areas_process(token: str, area_name: str, process_type: str) -> Dict[str, Any]: return request_json("POST", "/database/getAreasProcess/", with_token(token, {"areaName": area_name, "processType": process_type}))
def db_get_cache_area_pose(token: str) -> Dict[str, Any]: return request_json("POST", "/database/getCacheAreaPose/", with_token(token, {}))
def db_get_consumable(token: str) -> Dict[str, Any]: return request_json("POST", "/database/getConsumable/", with_token(token, {}))
def db_get_current_waypoint(token: str) -> Dict[str, Any]: return request_json("POST", "/database/getCurrentWaypoint/", with_token(token, {}))
def db_get_eoats(token: str) -> Dict[str, Any]: return request_json("POST", "/database/getEOATs/", with_token(token, {}))
def db_get_links_process(token: str, link: str) -> Dict[str, Any]: return request_json("POST", "/database/getLinksProcess/", with_token(token, {"link": link}))
def db_get_log_data(token: str, start_date: str, end_date: str, level: str) -> Dict[str, Any]: return request_json("POST", "/database/getLogData/", with_token(token, {"startDate": start_date, "endDate": end_date, "level": level}))
def db_get_real_name_list(token: str) -> Dict[str, Any]: return request_json("POST", "/database/getRealNameList/", with_token(token, {}))
def db_get_waypoints(token: str, area_name: str, pose: str) -> Dict[str, Any]: return request_json("POST", "/database/getWaypoints/", with_token(token, {"areaName": area_name, "Pose": pose}))
def db_save_consumable(token: str, id: str, consumable_type: str, name: str, wells: str, offset_inside_z: str, offset_uncover_z: str, offset_lid_bottom: str, offset_covered: str, cover_squeexe: str, offset_bottom: str, squeeze: str, unsqueeze: str) -> Dict[str, Any]: return request_json("POST", "/database/saveConsumable/", with_token(token, {"id": id, "consumableType": consumable_type, "name": name, "wells": wells, "offsetInsideZ": offset_inside_z, "offsetUncoverZ": offset_uncover_z, "offsetLidBottom": offset_lid_bottom, "offsetCovered": offset_covered, "cover_squeexe": cover_squeexe, "offsetBottom": offset_bottom, "squeeze": squeeze, "unsqueeze": unsqueeze}))
def db_save_new_link(token: str, link_name: str, area_from: str, area_to: str, pose_from: str, pose_to: str) -> Dict[str, Any]: return request_json("POST", "/database/saveNewLink/", with_token(token, {"linkNmae": link_name, "areaFrom": area_from, "areaTo": area_to, "poseFrom": pose_from, "poseTo": pose_to}))
def db_save_waypoint(token: str, area_name: str, pose: str, waypoint: str) -> Dict[str, Any]: return request_json("POST", "/database/saveWaypoint/", with_token(token, {"areaName": area_name, "Pose": pose, "waypoint": waypoint}))
def db_stack_continuation(token: str) -> Dict[str, Any]: return request_json("POST", "/database/stackContinuation/", with_token(token, {}))
def db_update_area(token: str, area_name_list: str, edit_area_eoat: str, area_forward: str, area_offset_z: str) -> Dict[str, Any]: return request_json("POST", "/database/updateArea/", with_token(token, {"areaNameList": area_name_list, "editAreaEOAT": edit_area_eoat, "areaForward": area_forward, "areaOffsetZ": area_offset_z}))
def db_update_consumable(token: str, id: str, consumable_type: str, name: str, wells: str, offset_inside_z: str, offset_uncover_z: str, offset_lid_bottom: str) -> Dict[str, Any]: return request_json("POST", "/database/updateConsumable/", with_token(token, {"id": id, "consumableType": consumable_type, "name": name, "wells": wells, "offsetInsideZ": offset_inside_z, "offsetUncoverZ": offset_uncover_z, "offsetLidBottom": offset_lid_bottom}))
def db_update_link_process(token: str, link: str, process_list: str) -> Dict[str, Any]: return request_json("POST", "/database/updateLinkProcess/", with_token(token, {"link": link, "processList": process_list}))
def db_update_process(token: str, area_name: str, process_type: str, process_list: str) -> Dict[str, Any]: return request_json("POST", "/database/updateProcess/", with_token(token, {"areaName": area_name, "processType": process_type, "processList": process_list}))


# --- initialization ---
def init_finalize(token: str) -> Dict[str, Any]: return request_json("POST", "/initialization/finalize/", with_token(token, {}))
def init_initialize(token: str, homed: Optional[int] = None, forced: Optional[int] = None) -> Dict[str, Any]: return request_json("POST", "/initialization/initialize/", with_token(token, _drop_none_fields({"homed": homed, "forced": forced})))
def init_is_initialized() -> Dict[str, Any]: return request_json("POST", "/initialization/isInitialized/", {})


# --- robotControl ---
def robot_forward(token: str, waypoint: Any) -> Dict[str, Any]: return request_json("POST", "/robotControl/forward/", with_token(token, {"waypoint": waypoint}))
def robot_inverse(token: str, waypoint: Any) -> Dict[str, Any]: return request_json("POST", "/robotControl/inverse/", with_token(token, {"waypoint": waypoint}))
def robot_keep_joints_tuning_alive(token: str) -> Dict[str, Any]: return request_json("POST", "/robotControl/keepJointsTuningAlive/", with_token(token, {}))
def robot_keep_motion_alive(token: str) -> Dict[str, Any]: return request_json("POST", "/robotControl/keepMotionAlive/", with_token(token, {}))
def robot_keep_pose_tuning_alive(token: str) -> Dict[str, Any]: return request_json("POST", "/robotControl/keepPoseTuningAlive/", with_token(token, {}))
def robot_move_camera_to_robot_offset(token: str, vel: float, acc: float) -> Dict[str, Any]: return request_json("POST", "/robotControl/moveCameraToRobotOffset/", with_token(token, {"vel": vel, "acc": acc}))
def robot_set_joints_stepping(token: str, steps: Any, velocity: float, acceleration: float) -> Dict[str, Any]: return request_json("POST", "/robotControl/setJointsStepping/", with_token(token, {"steps": steps, "velocity": velocity, "acceleration": acceleration}))
def robot_set_joints_tuning(token: str, directions: Any, velocity: float, acceleration: float) -> Dict[str, Any]: return request_json("POST", "/robotControl/setJointsTuning/", with_token(token, {"directions": directions, "velocity": velocity, "acceleration": acceleration}))
def robot_set_motion(token: str, waypoint: Any, motion: str, vel: float, acc: float) -> Dict[str, Any]: return request_json("POST", "/robotControl/setMotion/", with_token(token, {"waypoint": waypoint, "motion": motion, "vel": vel, "acc": acc}))
def robot_set_pose_stepping(token: str, steps: Any, velocity: float, acceleration: float) -> Dict[str, Any]: return request_json("POST", "/robotControl/setPoseStepping/", with_token(token, {"steps": steps, "velocity": velocity, "acceleration": acceleration}))
def robot_set_pose_tuning(token: str, directions: Any, velocity: float, acceleration: float) -> Dict[str, Any]: return request_json("POST", "/robotControl/setPoseTuning/", with_token(token, {"directions": directions, "velocity": velocity, "acceleration": acceleration}))
def robot_set_robot_coordinate_by_name(token: str, name: str) -> Dict[str, Any]: return request_json("POST", "/robotControl/setRobotCoordinateByName/", with_token(token, {"name": name}))
def robot_shutdown(token: str) -> Dict[str, Any]: return request_json("POST", "/robotControl/shutdown/", with_token(token, {}))
def robot_stop_joints_tuning(token: str) -> Dict[str, Any]: return request_json("POST", "/robotControl/stopJointsTuning/", with_token(token, {}))
def robot_stop_motion(token: str) -> Dict[str, Any]: return request_json("POST", "/robotControl/stopMotion/", with_token(token, {}))
def robot_stop_pose_tuning(token: str) -> Dict[str, Any]: return request_json("POST", "/robotControl/stopPoseTuning/", with_token(token, {}))


# --- script-api ---
def script_api_align_location(token: str, area: str) -> Dict[str, Any]: return request_json("POST", "/script-api/alignLocation/", with_token(token, {"area": area}))
def script_api_battery() -> Dict[str, Any]: return request_json("POST", "/script-api/battery/", {})
def script_api_calc_pose_base_location(token: str, current_pos: Any, base_pos: Any, target_pos: Any) -> Dict[str, Any]: return request_json("POST", "/script-api/calcPoseBaseLocation/", with_token(token, {"current_pos": current_pos, "base_pos": base_pos, "target_pos": target_pos}))
def script_api_calibrate_location(token: str, area: str) -> Dict[str, Any]: return request_json("POST", "/script-api/calibrateLocation/", with_token(token, {"area": area}))
def script_api_clear_cur_location_offset(token: str) -> Dict[str, Any]: return request_json("POST", "/script-api/clearCurLocationOffset/", with_token(token, {}))
def script_api_cur_location(token: str) -> Dict[str, Any]: return request_json("POST", "/script-api/curLocation/", with_token(token, {}))
def script_api_cur_location_offset(token: str) -> Dict[str, Any]: return request_json("POST", "/script-api/curLocationOffset/", with_token(token, {}))
def script_api_cur_lock(token: str) -> Dict[str, Any]: return request_json("POST", "/script-api/curLock/", with_token(token, {}))
def script_api_current_pose(token: str, model: str) -> Dict[str, Any]: return request_json("POST", "/script-api/currentPose/", with_token(token, {"model": model}))
def script_api_forward(token: str, waypoint: Any) -> Dict[str, Any]: return request_json("POST", "/script-api/forward/", with_token(token, {"waypoint": waypoint}))
def script_api_get_consumable(token: str, consumable: int) -> Dict[str, Any]: return request_json("POST", "/script-api/getConsumable/", with_token(token, {"consumable": consumable}))
def script_api_grip_action(token: str, action_type: str, value: int, grasp: Optional[int] = None, access: Optional[int] = None) -> Dict[str, Any]: return request_json("POST", "/script-api/gripAction/", with_token(token, _drop_none_fields({"actionType": action_type, "value": value, "grasp": grasp, "access": access})))
def script_api_inverse(token: str, waypoint: Any) -> Dict[str, Any]: return request_json("POST", "/script-api/inverse/", with_token(token, {"waypoint": waypoint}))
def script_api_location_offset(token: str, area: str) -> Dict[str, Any]: return request_json("POST", "/script-api/locationOffset/", with_token(token, {"area": area}))
def script_api_move(token: str, waypoint: Any, motion: str, vel: float, acc: float) -> Dict[str, Any]: return request_json("POST", "/script-api/move/", with_token(token, {"waypoint": waypoint, "motion": motion, "vel": vel, "acc": acc}))
def script_api_move_to(token: str, location: str, vel: float, acc: float) -> Dict[str, Any]: return request_json("POST", "/script-api/moveTo/", with_token(token, {"location": location, "vel": vel, "acc": acc}))
def script_api_peripheral_action(token: str, peripheral: str, action_type: str, value: str) -> Dict[str, Any]: return request_json("POST", "/script-api/peripheralAction/", with_token(token, {"peripheral": peripheral, "actionType": action_type, "value": value}))
def script_api_pose(token: str, area: str, pose: str) -> Dict[str, Any]: return request_json("POST", "/script-api/pose/", with_token(token, {"area": area, "pose": pose}))
def script_api_reset_robot(token: str, recover: int, clear: int) -> Dict[str, Any]: return request_json("POST", "/script-api/resetRobot/", with_token(token, {"recover": recover, "clear": clear}))
def script_api_set_cur_location_offset(token: str, location: str, name: str, location_offset: Any) -> Dict[str, Any]: return request_json("POST", "/script-api/setCurLocationOffset/", with_token(token, {"location": location, "name": name, "location_offset": location_offset}))
def script_api_teach(token: str, pose: Any) -> Dict[str, Any]: return request_json("POST", "/script-api/teach/", with_token(token, {"pose": pose}))


# --- script ---
def script_delete(token: str, name: str) -> Dict[str, Any]: return request_json("POST", "/script/delete/", with_token(token, {"name": name}))
def script_exec(token: str, contents: str, arguments: Optional[str] = None) -> Dict[str, Any]: return request_json("POST", "/script/exec/", with_token(token, _drop_none_fields({"contents": contents, "arguments": arguments})))
def script_exec_by_name(token: str, name: str, arguments: Optional[str] = None) -> Dict[str, Any]: return request_json("POST", "/script/execByName/", with_token(token, _drop_none_fields({"name": name, "arguments": arguments})))
def script_save(token: str, name: str, contents: str) -> Dict[str, Any]: return request_json("POST", "/script/save/", with_token(token, {"name": name, "contents": contents}))
def script_get(token: str, name: str) -> Dict[str, Any]: return request_json("POST", "/script/get/", with_token(token, {"name": name}))
def script_list(token: str) -> Dict[str, Any]: return request_json("POST", "/script/list/", with_token(token, {}))
def script_status(token: str) -> Dict[str, Any]: return request_json("POST", "/script/status/", with_token(token, {}))
def script_stop(token: str) -> Dict[str, Any]: return request_json("POST", "/script/stop/", with_token(token, {}))


# --- synchronization ---
def sync_area() -> Dict[str, Any]:
    return request_json("GET", "/synchronization/area/", {})
