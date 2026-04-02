---
name: skill-robot-control
description: |
  通过 scripts/validate.py 控制汇像机器人与 AGV，兼容 legacy 命令与 namespaced 命令。
  触发词（融合）：初始化/夹爪/Perform/安全位/急停/相机/AGV移动/状态查询/关闭机器人/示教系统API/数据库与配置/脚本执行。
  排除条件：仅需讲解原理；请求未封装能力；参数缺失且无法补齐；要求绕过权限或安全门禁。
---

# 机器人控制 Skill（OpenClaw）

## 目标
将自然语言请求准确映射为 `python scripts/validate.py <subcommand> [args]`，并返回可追溯 JSON 结果。

## 能力范围（融合分层）

### L1：Legacy 稳定命令（优先兼容）
- 初始化与状态：`init_all`、`status`、`close_robot`
- 运动与执行：`perform`、`safe`、`shutdown`
- 夹爪与相机：`grip_open`、`grip_close`、`grip_position`、`camera`
- AGV 基础：`agv_goto`、`vehicle_stop`、`vehicle_home`、`vehicle_location`

### L2：Namespaced 扩展命令（按域分组）
- 访问与权限：`access_*`、`authority_*`
- 动作与控制：`action_*`、`command_*`、`robot_*`
- 配置与数据库：`config_*`、`db_*`、`sync_*`
- 初始化与脚本：`init_*`、`script_*`、`script_api_*`

### L3：融合原则（必须遵守）
1. Legacy 命令语义、默认参数和执行路径保持兼容。
2. 新能力使用 namespaced 命令，不替换 legacy 命令名。
3. 两类命令统一通过 `validate.py` 入口执行，统一 JSON 返回结构。

## 触发策略（分层）

### 直接触发（可执行）
- 用户明确要求“真实执行动作/查询状态”，且参数齐全、安全条件可确认。

### 先澄清再执行
- 动作目标不明确（如未给 `perform target`、`agv_goto location`、`grip_position value`）。
- namespaced 命令的复杂参数未给完整 JSON。

### 不触发执行
- 用户仅需解释、学习、方案讨论。
- 请求未封装接口或要求绕过 token/控制权/安全门禁。

## 参数收集规则（保留并细化）

### A. Legacy 关键参数
- `grip_position`：必须 `value:int`
- `perform`：必须 `target`；可选 `vel:int=30`、`acc:int=30`、`wait:int=0`
  - `wait=0`：异步发送，立即返回（长动作推荐）
  - `wait=1`：同步等待完成
- `safe`：可选 `target`，默认 `Safe`
- `camera`：可选 `out`
- `agv_goto`：必须 `location`

### B. Namespaced 参数规范
- 简单字段：按 `--name value` 传入。
- 复杂字段必须传 JSON 字符串（如 `waypoint`、`poses`、`steps`、`directions`、`process_list`、`configurations`、`location_offset` 等）。
- 数值字段应能安全转换为 `int/float`；无法转换应返回参数错误。
- 可选字段不应强行传 `None`。

### C. Token 与就绪策略
- 未传 `--token`：按命令类型自动走状态文件与保障逻辑（token-only 或 ready-required）。
- 不需 token 的查询接口直接调用（如部分 `config_*`、`sync_*`、`script_api_battery` 等）。

## 安全门禁（必须执行）
对会触发真实运动/状态变化的命令（含 `grip_*`、`perform`、`safe`、`shutdown`、`agv_goto`、`vehicle_*`、多数 `action_*`/`command_*`/`robot_*`/操作型 `script_api_*`）：
1. 确认危险区域无人、路径无遮挡。
2. 确认夹爪/机械臂/AGV 运动不会伤人或撞机。
3. 确认急停可达。
4. 用户明确“允许真实执行”。

若任一条件无法确认：仅返回原因与建议，不执行动作。

## 输出与执行约束
- 执行格式：`python scripts/validate.py <subcommand> [args]`
- 成功输出：`{"success": true, "command": "...", "result": ...}`
- 失败输出：`{"success": false, "error": "..."}`
- 仅在命令映射清晰、参数齐全、安全确认完成后执行。