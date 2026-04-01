---
name: skill-robot-control
description: |
  通过本地脚本 scripts/validate.py 控制汇像机器人与下装移动工具（AGV）动作，支持 legacy 命令与 namespaced 命令（access_/action_/authority_/command_/config_/db_/init_/robot_/script_api_/script_/sync_）。
  触发词：初始化机器人｜打开夹爪｜关闭夹爪｜夹爪移动到｜执行 Perform｜回安全位｜获取相机图片｜机器人急停｜下装移动到站点｜停止运动｜移动工具回零｜获取移动工具位置｜关闭机器人｜查看状态｜数据库配置查询｜脚本执行｜示教系统接口
  排除条件：仅解释原理/代码；讨论架构方案；请求未封装复杂流程；要求绕过权限/安全；动作目标不明确却要求直接执行。
---

# 机器人控制 Skill（OpenClaw）

## 目标
将用户自然语言请求映射为 `scripts/validate.py` 子命令，返回真实执行结果（JSON），保持可追溯、可复现。

## 能力范围（与脚本严格一致）
- 基础控制：`init_all`、`grip_open`、`grip_close`、`grip_position value`、`perform target [--vel] [--acc] [--wait]`、`safe [--target]`、`shutdown`、`camera [--out]`、`status`
- 下装移动工具：`agv_goto location`、`vehicle_stop`、`vehicle_home`、`vehicle_location`
- 系统控制：`close_robot`
- Namespaced 接口：
  - `access_*`
  - `action_*`
  - `authority_*`
  - `command_*`
  - `config_*`
  - `db_*`
  - `init_*`
  - `robot_*`
  - `script_api_*`
  - `script_*`
  - `sync_*`

> 只调用 validate.py 已封装子命令；不自动扩展未封装接口。

## 何时触发
当用户明确要求执行上述命令对应的真实动作或状态查询时触发。

## 何时不要触发
- 用户只需要讲解、学习资料、架构建议。
- 用户要求执行脚本未封装动作。
- 用户未提供必要参数（如 `grip_position value`、`perform target`、`agv_goto location`）。
- 用户要求绕过 token、控制权或安全确认。

## 参数收集规则
- `grip_position`：必须 `value`（int）
- `perform`：必须 `target`；可选 `vel`(默认 30)、`acc`(默认 30)、`wait`(默认 0，异步模式)
  - `wait=0`: 火发模式 (fire-and-forget)，发送指令后立即返回（推荐用于长时间动作）
  - `wait=1`: 同步模式，等待动作完成后再返回（用于需要确认的场景）
- `safe`：可选 `target`（默认 `Safe`）
- `camera`：可选 `out`
- `agv_goto`：必须 `location`（如 `LM1`、`LM7`）
- 其他命令无需额外参数
- namespaced 命令中复杂参数（如 `waypoint`、`poses`、`process_list`、`configurations` 等）必须按 JSON 字符串传入。
- namespaced 命令如显式提供 `--token` 则优先使用；未提供时按脚本策略自动从状态和保障逻辑获取。

## 安全门禁（必须执行）
对会触发真实运动/控制变化的命令（`grip_*`、`perform`、`safe`、`shutdown`、`agv_goto`、`vehicle_stop`、`vehicle_home`、`close_robot`）：
1. 确认危险区域无人、路径无障碍。
2. 确认夹爪与机器人运动不会伤人/撞机。
3. 确认急停可触达。
4. 用户明确"要真实执行"。

若无法确认安全，只给出原因，不执行动作。

## 命令映射
- "初始化机器人/测试初始化链路" → `init_all`
- "打开夹爪" → `grip_open`
- "关闭夹爪" → `grip_close`
- "夹爪移动到 300" → `grip_position 300`
- "在 A 区域执行 Perform" → `perform A [--vel --acc --wait]`
- "回安全位" → `safe [--target Safe]`
- "急停机器人" → `shutdown`
- "获取相机图片" → `camera [--out path]`
- "下装移动到 LM7" → `agv_goto LM7`
- "停止移动工具" → `vehicle_stop`
- "移动工具回零" → `vehicle_home`
- "移动工具在哪" → `vehicle_location`
- "关闭机器人/释放控制权" → `close_robot`
- "查看当前状态" → `status`
- "调用示教系统 namespaced API" → `python scripts/validate.py <namespaced_subcommand> [--args]`

## 执行约束
- 默认执行格式：`python scripts/validate.py <subcommand> [args]`
- 保持脚本现有 JSON 输出结构：
  - 成功：`{"success": true, "command": "...", "result": ...}`
  - 失败：`{"success": false, "error": "..."}`
- 仅在命令被清晰映射且参数齐全时执行。

## 异步执行说明
对于 `perform` 等长时间动作，默认使用 `wait=0` 异步模式：
- 指令发送到机器人后立即返回
- 即使网络超时，也可能已经成功执行
- 可通过 `查看状态` 或重新初始化来确认机器人当前状态
- 如需等待完成，显式指定 `--wait 1`
