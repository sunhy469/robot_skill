"""OpenClaw 机器人 Skill CLI 入口（兼容壳）。"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any, Callable, Dict

from robot_actions import (
    cmd_agv_goto_location,
    cmd_camera,
    cmd_close_robot,
    cmd_get_current_location,
    cmd_grip_close,
    cmd_grip_open,
    cmd_grip_position,
    cmd_init_all,
    cmd_perform,
    cmd_safe,
    cmd_shutdown,
    cmd_status,
    cmd_vehicle_home,
    cmd_vehicle_stop,
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="validate.py",
        description="汇像机器人控制脚本，供 OpenClaw Skill 调用",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init_all", help="执行完整初始化流程")
    sub.add_parser("grip_open", help="打开夹爪")
    sub.add_parser("grip_close", help="关闭夹爪")

    p_grip = sub.add_parser("grip_position", help="夹爪移动到指定位置")
    p_grip.add_argument("value", type=int, help="夹爪位置值")

    p_perform = sub.add_parser("perform", help="执行目标区域动作")
    p_perform.add_argument("target", help="目标区域名称")
    p_perform.add_argument("--vel", type=int, default=30, help="速度百分比")
    p_perform.add_argument("--acc", type=int, default=30, help="加速度百分比")
    p_perform.add_argument("--wait", type=int, default=1, help="是否等待完成，1 等待，0 不等待")

    p_safe = sub.add_parser("safe", help="回安全位")
    p_safe.add_argument("--target", default="Safe", help="安全位名称")

    sub.add_parser("shutdown", help="急停")

    p_camera = sub.add_parser("camera", help="获取相机图片")
    p_camera.add_argument("--out", default=None, help="保存图片到指定路径")

    sub.add_parser("close_robot", help="关闭机器人并重置本地状态")
    sub.add_parser("status", help="查看本地状态")

    p_agv = sub.add_parser("agv_goto", help="下装移动工具运动到指定站点")
    p_agv.add_argument("location", help="站点名称，如 LM1, LM7")

    sub.add_parser("vehicle_stop", help="停止下装移动工具运动")
    sub.add_parser("vehicle_home", help="下装移动工具回零")
    sub.add_parser("vehicle_location", help="获取当前下装移动工具位置")
    return parser


def main() -> int:
    _setup_logging()
    parser = build_parser()
    args = parser.parse_args()

    command_handlers: Dict[str, Callable[[], Dict[str, Any]]] = {
        "init_all": cmd_init_all,
        "grip_open": cmd_grip_open,
        "grip_close": cmd_grip_close,
        "grip_position": lambda: cmd_grip_position(args.value),
        "perform": lambda: cmd_perform(args.target, args.vel, args.acc, args.wait),
        "safe": lambda: cmd_safe(args.target),
        "shutdown": cmd_shutdown,
        "camera": lambda: cmd_camera(args.out),
        "close_robot": cmd_close_robot,
        "status": cmd_status,
        "agv_goto": lambda: cmd_agv_goto_location(args.location),
        "vehicle_stop": cmd_vehicle_stop,
        "vehicle_home": cmd_vehicle_home,
        "vehicle_location": cmd_get_current_location,
    }

    try:
        if args.command not in command_handlers:
            raise RobotApiError(f"未知命令：{args.command}")

        result = command_handlers[args.command]()
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
