---
name: skill-robot-control
description: |
  通过 scripts/validate.py 控制汇像机器人与 AGV，统一使用 namespaced 命令。
  本文件为"总入口"，详细指令拆分到 docs/ 子文档：快速开始、安全/故障、步进运动、命令清单。
  触发词：初始化/夹爪/Perform/安全位/急停/相机/AGV 移动/状态查询/关闭机器人/数据库与配置/脚本执行/步进模式。
  排除条件：仅需原理讲解；参数缺失且无法补齐；请求绕过 token/安全门禁。
---

# 机器人控制 Skill（OpenClaw）

> 已按你的反馈继续精简：删除"区域流程"专题，并将"安全门禁 + 故障排查"合并为单文档，减少跳转成本。

## 1. 使用原则（必须遵守）

所有命令统一走以下链路：

1. `scripts/validate.py`：解析 CLI 参数、校验必填项。
2. `scripts/robot_actions.py`：参数类型转换（JSON/float/int）、token 策略。
3. `scripts/robot_core.py`：拼装 HTTP payload，调用具体 API endpoint。

统一命令格式：

```bash
python scripts/validate.py <subcommand> [args]
```

统一返回 JSON：
- 成功：`{"success": true, "command": "...", "result": ...}`
- 失败：`{"success": false, "error": "..."}`

---

## 2. 文档导航（最终精简版）

- 快速开始与执行编排：`docs/quickstart.md`
- 安全门禁 + 故障排查：`docs/safety.md`
- 机械臂步进运动（Pose/Joints）：`docs/motion_stepping.md`
- 命令清单（初始化/action/command/robot/agv 移动）：`docs/command_catalog.md`

> 规则：只加载当前任务必需的专题文档，避免一次性读取所有内容。

---

## 3. 标准执行流程（对话到落地）

1. 识别用户意图，匹配命令分组（初始化 / action_* / command_* / robot_*）。
2. 读取必要专题文档并收集必填参数。
3. 执行安全门禁检查（详见 `docs/safety.md`）。
4. 生成并执行 CLI 命令。
5. 返回标准 JSON；必要时附带停止/释放控制权建议。

---

## 4. Token / 初始化 / 权限（摘要）

- `--token` 可显式传入。
- 未传 token 时：
  - 普通场景：`ensure_token_ready()` 自动申请/复用控制权。
  - 运动场景：`ensure_initialized()` 自动确保初始化后执行。
- 建议流程：
  1. `authority_generate --forced 1`
  2. 执行动作命令
  3. `authority_consume` 释放控制权

更多细节：`docs/quickstart.md`

---

## 5. 参数规则（摘要）

- 必填以 `validate.py` 中 `required=True` 为准。
- 结构化字段必须传 JSON 字符串（如 `steps / waypoint / poses / directions / configurations`）。
- 数值字段（如 `velocity / acceleration / vel / acc`）会转为 `float`，失败则直接报参数错误。

示例：

```bash
--steps '[0.0, 0.0, 5.0, 0.0, 0.0, 0.0]'
```

---

## 6. 高频语义映射（摘要）

- "打开夹爪" → `action_grip_control --action_type Open --value 0`
- "关闭夹爪" → `action_grip_control --action_type Close --value 0`
- "执行区域动作/perform" → `command_perform --target <target> [--vel --acc --wait]`
- "回安全位" → `command_return_to_safe --target Safe`
- "急停/停机" → `robot_shutdown`
- "停止当前运动" → `robot_stop_motion`
- "相机抓拍" → `action_get_camera_jpg`
- "AGV 去站点" → `action_agv_goto_location --location <name>`

完整清单：`docs/command_catalog.md`

---

## 7. 专题跳转建议

- 用户提"机械臂上/下/前/后、左倾，右倾，抬头，低头，左旋，右旋多少度" → `docs/motion_stepping.md`
- 用户提"下装工具 agv 向前移动，左转，右转" → `docs/command_catalog.md`
- 用户提"报错了、参数不对、网络失败、是否可执行" → `docs/safety.md`
- 任意真实运动或状态改变请求 → 先看 `docs/safety.md`

---
