"""
汇像机器人控制脚本 validate.py

用途：
1. 作为 OpenClaw Skill 的底层执行脚本；
2. 封装当前已经联调通过的汇像机器人 HTTP API；
3. 通过命令行方式供 OpenClaw 调用；
4. 使用 robot_state.json 持久化 token 和初始化状态。

"""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any, Dict, Optional

import requests


# =========================
# 固定配置
# =========================

BASE_URL = "http://192.168.193.10:8300"
API_TIMEOUT = 5.0
STATE_FILE = os.path.join(os.path.dirname(__file__), "robot_state.json")


# =========================
# 异常定义
# =========================

class RobotApiError(RuntimeError):
    """机器人接口调用异常。"""
    pass


# =========================
# 工具函数
# =========================

def json_dumps(data: Any) -> str:
    """
    将对象格式化为 JSON 字符串，便于 OpenClaw 读取。

    参数：
        data: 任意 Python 对象

    返回：
        str: 格式化后的 JSON 字符串
    """
    try:
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception:
        return str(data)


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


def now_ts() -> int:
    """
    获取当前时间戳。

    返回：
        int: 秒级时间戳
    """
    return int(time.time())


# =========================
# 本地状态文件操作
# =========================

def default_state() -> Dict[str, Any]:
    """
    返回默认状态。

    返回：
        Dict[str, Any]: 默认状态字典
    """
    return {
        "token": "",
        "initialized": False,
        "last_update": 0
    }


def load_state() -> Dict[str, Any]:
    """
    从 robot_state.json 读取本地状态。

    返回：
        Dict[str, Any]: 状态字典；如果文件不存在或解析失败，返回默认状态
    """
    if not os.path.exists(STATE_FILE):
        return default_state()

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            state = default_state()
            state.update(data if isinstance(data, dict) else {})
            return state
    except Exception:
        return default_state()


def save_state(token: Optional[str] = None, initialized: Optional[bool] = None) -> Dict[str, Any]:
    """
    保存本地状态到 robot_state.json。

    参数：
        token: 新 token；为 None 时沿用旧值
        initialized: 新初始化状态；为 None 时沿用旧值

    返回：
        Dict[str, Any]: 保存后的状态字典
    """
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
    """
    将本地状态文件全部归位。

    归位内容：
    - token 清空
    - initialized 置为 False
    - 更新时间刷新

    返回：
        Dict[str, Any]: 重置后的状态字典
    """
    state = {
        "token": "",
        "initialized": False,
        "last_update": now_ts()
    }

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    return state


# =========================
# HTTP 请求基础函数
# =========================

def request_json(method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    发送 JSON 请求，并返回 JSON 响应。

    参数：
        method: 请求方法，如 POST、GET
        path: 接口路径
        payload: 请求体字典

    返回：
        Dict[str, Any]: 响应 JSON

    异常：
        RobotApiError: 请求失败、HTTP 状态异常或响应 JSON 非法时抛出
    """
    url = join_url(BASE_URL, path)
    payload = payload or {}

    try:
        response = requests.request(
            method=method.upper(),
            url=url,
            json=payload,
            timeout=API_TIMEOUT
        )
    except requests.RequestException as e:
        raise RobotApiError(f"请求失败：{method} {url}，错误：{e}") from e

    if response.status_code != 200:
        try:
            error_data = response.json()
        except Exception:
            error_data = response.text
        raise RobotApiError(f"接口返回异常：HTTP {response.status_code}，内容：{json_dumps(error_data)}")

    try:
        data = response.json()
    except Exception as e:
        raise RobotApiError(f"响应不是合法 JSON：{response.text}") from e

    if isinstance(data, dict) and data.get("success") is False:
        raise RobotApiError(f"接口业务返回失败：{json_dumps(data)}")

    return data


def request_bytes(method: str, path: str) -> bytes:
    """
    发送请求并返回二进制数据，主要用于下载相机图片。

    参数：
        method: 请求方法
        path: 图片路径或完整 URL

    返回：
        bytes: 二进制内容
    """
    url = join_url(BASE_URL, path)

    try:
        response = requests.request(
            method=method.upper(),
            url=url,
            timeout=API_TIMEOUT
        )
    except requests.RequestException as e:
        raise RobotApiError(f"下载失败：{method} {url}，错误：{e}") from e

    if response.status_code != 200:
        raise RobotApiError(f"下载图片失败：HTTP {response.status_code}，内容：{response.text}")

    return response.content


def require_token(token: str) -> None:
    """
    检查 token 是否为空。

    参数：
        token: token 字符串

    异常：
        RobotApiError: token 为空时抛出
    """
    if not token:
        raise RobotApiError("当前没有 token，请先初始化机器人。")


def with_token(token: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    在请求体中附加 token。

    参数：
        token: token 字符串
        payload: 原始请求体

    返回：
        Dict[str, Any]: 附加 token 后的请求体
    """
    require_token(token)
    payload = payload or {}
    payload["token"] = token
    return payload


# =========================
# 汇像机器人 API 函数
# =========================

def generate_token(forced: int = 1) -> Dict[str, Any]:
    """
    获取机器人控制 token。

    参数：
        forced: 是否强制获取控制权，1 表示强制，0 表示非强制

    返回：
        Dict[str, Any]: 接口返回结果
    """
    payload = {
        "robot": "",
        "mode": "",
        "serial": "",
        "forced": int(forced)
    }
    return request_json("POST", "/authority/generate/", payload)


def consume_token(token: str) -> Dict[str, Any]:
    """
    销毁 token，释放控制权。

    参数：
        token: 当前控制 token

    返回：
        Dict[str, Any]: 接口返回结果
    """
    payload = with_token(token, {})
    return request_json("POST", "/authority/consume/", payload)


def is_accessible(token: str) -> Dict[str, Any]:
    """
    检查 token 是否有效。

    参数：
        token: 当前控制 token

    返回：
        Dict[str, Any]: 接口返回结果
    """
    payload = with_token(token, {})
    return request_json("POST", "/authority/isAccessible/", payload)


def is_controller(token: str) -> Dict[str, Any]:
    """
    检查 token 是否拥有控制权。

    参数：
        token: 当前控制 token

    返回：
        Dict[str, Any]: 接口返回结果
    """
    payload = with_token(token, {})
    return request_json("POST", "/authority/isController/", payload)


def initialize_robot(token: str, homed: int = 1, forced: int = 0) -> Dict[str, Any]:
    """
    初始化机器人。

    参数：
        token: 当前控制 token
        homed: 是否在初始化时运动到全局安全位
        forced: 是否强制初始化

    返回：
        Dict[str, Any]: 接口返回结果
    """
    payload = with_token(token, {
        "homed": int(homed),
        "forced": int(forced)
    })
    return request_json("POST", "/initialization/initialize/", payload)


def finalize_robot(token: str) -> Dict[str, Any]:
    """
    反初始化机器人。

    参数：
        token: 当前控制 token

    返回：
        Dict[str, Any]: 接口返回结果
    """
    payload = with_token(token, {})
    return request_json("POST", "/initialization/finalize/", payload)


def is_initialized() -> Dict[str, Any]:
    """
    查询机器人初始化状态。

    常见状态：
        0 = 未初始化
        1 = 初始化中
        2 = 已初始化

    返回：
        Dict[str, Any]: 接口返回结果
    """
    return request_json("POST", "/initialization/isInitialized/", {})


def reset_robot(token: str, recover: int = 1, clear: int = 1) -> Dict[str, Any]:
    """
    重置机器人事件。

    参数：
        token: 当前控制 token
        recover: 是否自动回安全位
        clear: 是否清除状态记录

    返回：
        Dict[str, Any]: 接口返回结果
    """
    payload = with_token(token, {
        "recover": int(recover),
        "clear": int(clear)
    })
    return request_json("POST", "/access/resetRobot/", payload)


def vehicle_reset(token: str) -> Dict[str, Any]:
    """
    重置下装移动工具错误。

    参数：
        token: 当前控制 token

    返回：
        Dict[str, Any]: 接口返回结果
    """
    payload = with_token(token, {})
    return request_json("POST", "/actionControl/vehicleReset/", payload)


def grip_control(token: str, action_type: str, value: int = 0) -> Dict[str, Any]:
    """
    控制夹爪动作。

    参数：
        token: 当前控制 token
        action_type: 动作类型，可选 Open / Close / Position
        value: 当 action_type=Position 时的目标值

    返回：
        Dict[str, Any]: 接口返回结果
    """
    payload = with_token(token, {
        "actionType": action_type,
        "value": value
    })
    return request_json("POST", "/actionControl/gripControl/", payload)


def grip_open(token: str) -> Dict[str, Any]:
    """
    打开夹爪。

    参数：
        token: 当前控制 token

    返回：
        Dict[str, Any]: 接口返回结果
    """
    return grip_control(token, "Open", 0)


def grip_close(token: str) -> Dict[str, Any]:
    """
    关闭夹爪。

    参数：
        token: 当前控制 token

    返回：
        Dict[str, Any]: 接口返回结果
    """
    return grip_control(token, "Close", 0)


def grip_position(token: str, value: int) -> Dict[str, Any]:
    """
    将夹爪开合到指定位置。

    参数：
        token: 当前控制 token
        value: 夹爪目标值

    返回：
        Dict[str, Any]: 接口返回结果
    """
    return grip_control(token, "Position", value)


def perform(token: str, target: str, vel: int = 30, acc: int = 30, wait: int = 1) -> Dict[str, Any]:
    """
    执行指定目标区域的动作流程。

    参数：
        token: 当前控制 token
        target: 目标区域名称
        vel: 速度百分比
        acc: 加速度百分比
        wait: 是否等待执行完成

    返回：
        Dict[str, Any]: 接口返回结果
    """
    payload = with_token(token, {
        "target": target,
        "vel": vel,
        "acc": acc,
        "wait": wait
    })
    return request_json("POST", "/command/perform/", payload)


def return_to_safe(token: str, target: str = "Safe") -> Dict[str, Any]:
    """
    控制机器人回到指定安全位。

    参数：
        token: 当前控制 token
        target: 安全位区域名称

    返回：
        Dict[str, Any]: 接口返回结果
    """
    payload = with_token(token, {
        "target": target
    })
    return request_json("POST", "/command/returnToSafe/", payload)


def shutdown_robot(token: str) -> Dict[str, Any]:
    """
    触发机器人急停。

    参数：
        token: 当前控制 token

    返回：
        Dict[str, Any]: 接口返回结果
    """
    payload = with_token(token, {})
    return request_json("POST", "/robotControl/shutdown/", payload)


def get_camera_jpg(token: str) -> Dict[str, Any]:
    """
    获取当前定位相机图片信息。

    参数：
        token: 当前控制 token

    返回：
        Dict[str, Any]: 接口返回结果
    """
    payload = with_token(token, {})
    return request_json("POST", "/actionControl/getCameraJpg/", payload)


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

    raise RobotApiError(f"相机返回结果中未找到 jpg 路径：{json_dumps(response_data)}")


def fetch_image_bytes(image_path: str) -> bytes:
    """
    根据图片路径下载图片二进制内容。

    参数：
        image_path: 图片路径或完整 URL

    返回：
        bytes: 图片二进制内容
    """
    return request_bytes("GET", image_path)


# =========================
# 下装移动工具 API 函数（新增）
# =========================

def agv_goto_location(token: str, location: str) -> Dict[str, Any]:
    """
    下装移动工具运动到对应站点。
    POST /actionControl/agvGotoLocation/

    参数：
        token: 当前控制 token
        location: 站点名，e.g. LM1, LM7

    返回：
        Dict[str, Any]: 接口返回结果
    """
    payload = with_token(token, {
        "location": str(location)
    })
    return request_json("POST", "/actionControl/agvGotoLocation/", payload)


def vehicle_stop(token: str) -> Dict[str, Any]:
    """
    下装移动工具运动停止。
    POST /actionControl/vehicleStop/

    参数：
        token: 当前控制 token

    返回：
        Dict[str, Any]: 接口返回结果
    """
    payload = with_token(token, {})
    return request_json("POST", "/actionControl/vehicleStop/", payload)


def vehicle_home(token: str) -> Dict[str, Any]:
    """
    下装移动工具回零。
    POST /actionControl/vehicleHome/

    参数：
        token: 当前控制 token

    返回：
        Dict[str, Any]: 接口返回结果
    """
    payload = with_token(token, {})
    return request_json("POST", "/actionControl/vehicleHome/", payload)


def get_current_location(token: str) -> Dict[str, Any]:
    """
    获取当前下装移动工具位置点。
    POST /script-api/curLocation/

    参数：
        token: 当前控制 token

    返回：
        Dict[str, Any]: 接口返回结果
    """
    payload = with_token(token, {})
    return request_json("POST", "/script-api/curLocation/", payload)


# =========================
# 状态检查与自动补齐
# =========================

def ensure_token_ready() -> str:
    """
    确保当前存在一个可用且具备控制权的 token。

    处理流程：
    1. 先从 robot_state.json 读取 token；
    2. 如果没有 token，则重新申请并保存；
    3. 如果已有 token，则检查是否有效、是否有控制权；
    4. 检查失败则重新申请 token 并保存。

    返回：
        str: 可用 token
    """
    state = load_state()
    token = state.get("token", "") or ""

    if not token:
        data = generate_token(forced=1)
        token = data.get("data").get("token")
        save_state(token=token)
        return token

    try:
        accessible = is_accessible(token)
        controller = is_controller(token)

        accessible_result = extract_result_value(accessible, "result", 0)
        controller_result = extract_result_value(controller, "result", 0)

        accessible_ok = str(accessible_result) == "1"
        controller_ok = str(controller_result) == "1"

        if accessible_ok and controller_ok:
            return token
    except Exception:
        pass

    data = generate_token(forced=1)
    token = data.get("data").get("token")
    save_state(token=token)
    return token


def ensure_initialized() -> str:
    """
    确保机器人已经完成初始化。

    处理流程：
    1. 先确保 token 可用；
    2. 查询机器人初始化状态；
    3. 如果已初始化，直接返回 token；
    4. 如果未初始化，则自动执行初始化流程并保存状态。

    返回：
        str: 可用 token
    """
    token = ensure_token_ready()

    state = is_initialized()
    raw_status = extract_result_value(state, "status", 0)

    try:
        status = int(raw_status)
    except Exception:
        status = 0

    if status == 2:
        save_state(token=token, initialized=True)
        return token

    try:
        vehicle_reset(token)
    except Exception:
        pass

    try:
        reset_robot(token, recover=1, clear=1)
    except Exception:
        pass

    initialize_robot(token, homed=1, forced=0)
    save_state(token=token, initialized=True)
    return token


def ensure_ready() -> str:
    """
    统一入口：确保 token 和初始化状态都已就绪。

    返回：
        str: 可用 token
    """
    return ensure_initialized()


# =========================
# 高层命令函数
# =========================

def cmd_init_all() -> Dict[str, Any]:
    """
    执行完整初始化流程。

    流程包括：
    1. 获取 token
    2. 重置下装错误
    3. 重置机器人事件
    4. 初始化机器人
    5. 保存本地状态

    返回：
        Dict[str, Any]: 各步骤结果
    """
    
    result: Dict[str, Any] = {}
    
    token_resp = generate_token(forced=1)
    token = token_resp.get("data").get("token")
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
    """
    获取相机图片，并可选保存到本地。

    参数：
        save_path: 图片保存路径，如果为None则使用默认路径

    返回：
        Dict[str, Any]: 相机结果、图片路径、保存信息
    """
    token = ensure_ready()
    camera_data = get_camera_jpg(token)
    jpg_path = extract_camera_jpg_path(camera_data)

    result = {
        "camera_response": camera_data,
        "jpg_path": jpg_path
    }

    # 默认保存路径
    if save_path is None:
        import os
        # 创建references目录如果不存在
        references_dir = os.path.join(os.path.dirname(__file__), "..", "references")
        os.makedirs(references_dir, exist_ok=True)
        save_path = os.path.join(references_dir, "current_view.jpg")
    
    # 保存图片（总是覆盖）
    content = fetch_image_bytes(jpg_path)
    with open(save_path, "wb") as f:
        f.write(content)
    result["saved_to"] = save_path

    return result


def cmd_close_robot() -> Dict[str, Any]:
    """
    关闭机器人，并将本地状态全部归位。

    关闭流程：
    1. 读取本地 token；
    2. 如果有 token，则先尝试反初始化 finalize；
    3. 再尝试销毁 token consume；
    4. 最后将 robot_state.json 里的 token、initialized 等状态全部归位。

    返回：
        Dict[str, Any]: 各步骤执行结果
    """
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


# =========================
# 下装移动工具高层命令函数（新增）
# =========================

def cmd_agv_goto_location(location: str) -> Dict[str, Any]:
    """
    执行下装移动工具运动到指定站点。

    参数：
        location: 站点名称，如 LM1, LM7

    返回：
        Dict[str, Any]: 接口返回结果
    """
    token = ensure_ready()
    return agv_goto_location(token, location)


def cmd_vehicle_stop() -> Dict[str, Any]:
    """
    停止下装移动工具运动。

    返回：
        Dict[str, Any]: 接口返回结果
    """
    token = ensure_ready()
    return vehicle_stop(token)


def cmd_vehicle_home() -> Dict[str, Any]:
    """
    下装移动工具回零。

    返回：
        Dict[str, Any]: 接口返回结果
    """
    token = ensure_ready()
    return vehicle_home(token)


def cmd_get_current_location() -> Dict[str, Any]:
    """
    获取当前下装移动工具位置。

    返回：
        Dict[str, Any]: 接口返回结果
    """
    token = ensure_ready()
    return get_current_location(token)


# =========================
# 命令行参数
# =========================

def build_parser() -> argparse.ArgumentParser:
    """
    构建命令行参数解析器。

    返回：
        argparse.ArgumentParser: 参数解析器对象
    """
    parser = argparse.ArgumentParser(
        prog="validate.py",
        description="汇像机器人控制脚本，供 OpenClaw Skill 调用"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_init_all = subparsers.add_parser("init_all", help="执行完整初始化流程")
    parser_init_all.set_defaults(command_name="init_all")

    parser_grip_open = subparsers.add_parser("grip_open", help="打开夹爪")
    parser_grip_open.set_defaults(command_name="grip_open")

    parser_grip_close = subparsers.add_parser("grip_close", help="关闭夹爪")
    parser_grip_close.set_defaults(command_name="grip_close")

    parser_grip_position = subparsers.add_parser("grip_position", help="夹爪移动到指定位置")
    parser_grip_position.add_argument("value", type=int, help="夹爪位置值")
    parser_grip_position.set_defaults(command_name="grip_position")

    parser_perform = subparsers.add_parser("perform", help="执行目标区域动作")
    parser_perform.add_argument("target", help="目标区域名称")
    parser_perform.add_argument("--vel", type=int, default=30, help="速度百分比")
    parser_perform.add_argument("--acc", type=int, default=30, help="加速度百分比")
    parser_perform.add_argument("--wait", type=int, default=1, help="是否等待完成，1 等待，0 不等待")
    parser_perform.set_defaults(command_name="perform")

    parser_safe = subparsers.add_parser("safe", help="回安全位")
    parser_safe.add_argument("--target", default="Safe", help="安全位名称")
    parser_safe.set_defaults(command_name="safe")

    parser_shutdown = subparsers.add_parser("shutdown", help="急停")
    parser_shutdown.set_defaults(command_name="shutdown")

    parser_camera = subparsers.add_parser("camera", help="获取相机图片")
    parser_camera.add_argument("--out", default=None, help="保存图片到指定路径")
    parser_camera.set_defaults(command_name="camera")

    parser_close_robot = subparsers.add_parser("close_robot", help="关闭机器人并重置本地状态")
    parser_close_robot.set_defaults(command_name="close_robot")

    parser_status = subparsers.add_parser("status", help="查看本地状态")
    parser_status.set_defaults(command_name="status")

    # ========== 新增下装移动工具命令 ==========
    parser_agv_goto = subparsers.add_parser("agv_goto", help="下装移动工具运动到指定站点")
    parser_agv_goto.add_argument("location", help="站点名称，如 LM1, LM7")
    parser_agv_goto.set_defaults(command_name="agv_goto")

    parser_vehicle_stop = subparsers.add_parser("vehicle_stop", help="停止下装移动工具运动")
    parser_vehicle_stop.set_defaults(command_name="vehicle_stop")

    parser_vehicle_home = subparsers.add_parser("vehicle_home", help="下装移动工具回零")
    parser_vehicle_home.set_defaults(command_name="vehicle_home")

    parser_vehicle_location = subparsers.add_parser("vehicle_location", help="获取当前下装移动工具位置")
    parser_vehicle_location.set_defaults(command_name="vehicle_location")

    return parser


# =========================
# 主入口
# =========================

def main() -> int:
    """
    脚本主入口。

    根据命令行参数分发到不同动作，并将结果以 JSON 输出到标准输出。

    返回：
        int: 进程退出码，0 表示成功，非 0 表示失败
    """
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command_name == "init_all":
            result = cmd_init_all()

        elif args.command_name == "grip_open":
            token = ensure_ready()
            result = grip_open(token)

        elif args.command_name == "grip_close":
            token = ensure_ready()
            result = grip_close(token)

        elif args.command_name == "grip_position":
            token = ensure_ready()
            result = grip_position(token, args.value)

        elif args.command_name == "perform":
            token = ensure_ready()
            result = perform(
                token=token,
                target=args.target,
                vel=args.vel,
                acc=args.acc,
                wait=args.wait
            )

        elif args.command_name == "safe":
            token = ensure_ready()
            result = return_to_safe(token, target=args.target)

        elif args.command_name == "shutdown":
            token = ensure_token_ready()
            result = shutdown_robot(token)
            save_state(token=token, initialized=False)

        elif args.command_name == "camera":
            result = cmd_camera(save_path=args.out)

        elif args.command_name == "close_robot":
            result = cmd_close_robot()

        elif args.command_name == "status":
            result = load_state()

        # ========== 新增下装移动工具命令处理 ==========
        elif args.command_name == "agv_goto":
            result = cmd_agv_goto_location(args.location)

        elif args.command_name == "vehicle_stop":
            result = cmd_vehicle_stop()

        elif args.command_name == "vehicle_home":
            result = cmd_vehicle_home()

        elif args.command_name == "vehicle_location":
            result = cmd_get_current_location()

        else:
            raise RobotApiError(f"未知命令：{args.command_name}")

        print(json_dumps({
            "success": True,
            "command": args.command_name,
            "result": result
        }))
        return 0

    except RobotApiError as e:
        print(json_dumps({
            "success": False,
            "error": str(e)
        }))
        return 2

    except Exception as e:
        print(json_dumps({
            "success": False,
            "error": f"未预期异常：{e}"
        }))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())