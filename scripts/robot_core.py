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
# 机器人底层 API（按官方域分组）
# =========================

# --- authority ---
def generate_token(forced: int = 1) -> Dict[str, Any]:
    return request_json("POST", "/authority/generate/", {"robot": "", "mode": "", "serial": "", "forced": int(forced)})


def consume_token(token: str) -> Dict[str, Any]:
    return request_json("POST", "/authority/consume/", with_token(token, {}))


def is_accessible(token: str) -> Dict[str, Any]:
    return request_json("POST", "/authority/isAccessible/", with_token(token, {}))


def is_controller(token: str) -> Dict[str, Any]:
    return request_json("POST", "/authority/isController/", with_token(token, {}))


# --- initialization ---
def initialize_robot(token: str, homed: int = 1, forced: int = 0) -> Dict[str, Any]:
    return request_json("POST", "/initialization/initialize/", with_token(token, {"homed": int(homed), "forced": int(forced)}))


def finalize_robot(token: str) -> Dict[str, Any]:
    return request_json("POST", "/initialization/finalize/", with_token(token, {}))


def is_initialized() -> Dict[str, Any]:
    return request_json("POST", "/initialization/isInitialized/", {})


# --- actionControl ---
def vehicle_reset(token: str) -> Dict[str, Any]:
    return request_json("POST", "/actionControl/vehicleReset/", with_token(token, {}))


def grip_control(token: str, action_type: str, value: int = 0) -> Dict[str, Any]:
    return request_json("POST", "/actionControl/gripControl/", with_token(token, {"actionType": action_type, "value": value}))


def grip_open(token: str) -> Dict[str, Any]:
    return grip_control(token, "Open", 0)


def grip_close(token: str) -> Dict[str, Any]:
    return grip_control(token, "Close", 0)


def grip_position(token: str, value: int) -> Dict[str, Any]:
    return grip_control(token, "Position", value)


def get_camera_jpg(token: str) -> Dict[str, Any]:
    return request_json("POST", "/actionControl/getCameraJpg/", with_token(token, {}))


def agv_goto_location(token: str, location: str) -> Dict[str, Any]:
    return request_json("POST", "/actionControl/agvGotoLocation/", with_token(token, {"location": str(location)}))


def vehicle_stop(token: str) -> Dict[str, Any]:
    return request_json("POST", "/actionControl/vehicleStop/", with_token(token, {}))


def vehicle_home(token: str) -> Dict[str, Any]:
    return request_json("POST", "/actionControl/vehicleHome/", with_token(token, {}))


# --- command ---
def perform(token: str, target: str, vel: int = 30, acc: int = 30, wait: int = 1) -> Dict[str, Any]:
    return request_json("POST", "/command/perform/", with_token(token, {"target": target, "vel": vel, "acc": acc, "wait": wait}))


def return_to_safe(token: str, target: str = "Safe") -> Dict[str, Any]:
    return request_json("POST", "/command/returnToSafe/", with_token(token, {"target": target}))


# --- robotControl ---
def shutdown_robot(token: str) -> Dict[str, Any]:
    return request_json("POST", "/robotControl/shutdown/", with_token(token, {}))


def reset_robot(token: str, recover: int = 1, clear: int = 1) -> Dict[str, Any]:
    return request_json("POST", "/access/resetRobot/", with_token(token, {"recover": int(recover), "clear": int(clear)}))


# --- script-api ---
def get_current_location(token: str) -> Dict[str, Any]:
    return request_json("POST", "/script-api/curLocation/", with_token(token, {}))


def extract_camera_jpg_path(response_data: Dict[str, Any]) -> str:
    data = response_data.get("data", {})
    if isinstance(data, dict) and data.get("jpg"):
        return str(data["jpg"])
    jpg = extract_result_value(response_data, "jpg", "")
    if jpg:
        return str(jpg)
    raise RobotBusinessError(f"相机返回结果中未找到 jpg 路径：{json_dumps(response_data)}")


def fetch_image_bytes(image_path: str) -> bytes:
    return request_bytes("GET", image_path)


# =========================
# token / 初始化保障逻辑
# =========================

def ensure_token_ready() -> str:
    state = load_state()
    token = state.get("token", "") or ""

    if not token:
        logger.info("ensure_token_ready: no local token, generating")
        data = generate_token(forced=1)
        new_token = extract_result_value(data, "token", "")
        if not new_token:
            raise RobotStateError(f"generate_token 未返回 token：{json_dumps(data)}")
        save_state(token=new_token)
        return str(new_token)

    try:
        accessible = str(extract_result_value(is_accessible(token), "result", 0)) == "1"
        controller = str(extract_result_value(is_controller(token), "result", 0)) == "1"
        if accessible and controller:
            logger.info("ensure_token_ready: reuse local token")
            return token
        logger.warning("ensure_token_ready: local token invalid, regenerating")
    except Exception as e:
        logger.warning("ensure_token_ready: token check failed: %s", e)

    data = generate_token(forced=1)
    new_token = extract_result_value(data, "token", "")
    if not new_token:
        raise RobotStateError(f"generate_token 未返回 token：{json_dumps(data)}")
    save_state(token=str(new_token))
    return str(new_token)


def ensure_initialized() -> str:
    token = ensure_token_ready()
    init_state = is_initialized()
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
        vehicle_reset(token)
    except Exception as e:
        logger.warning("vehicle_reset failed (degraded): %s", e)
    try:
        reset_robot(token, recover=1, clear=1)
    except Exception as e:
        logger.warning("reset_robot failed (degraded): %s", e)

    initialize_robot(token, homed=1, forced=0)
    save_state(token=token, initialized=True)
    return token


def ensure_ready() -> str:
    return ensure_initialized()
