---
name: skill-robot-control
description: |
  通过 scripts/validate.py 控制汇像机器人与 AGV，统一使用 namespaced 命令。
  支持：初始化、控制权、机械臂运动、夹爪/外围设备、AGV、数据库配置、脚本系统、状态查询与同步。
  触发词：初始化/夹爪/Perform/安全位/急停/相机/AGV移动/状态查询/关闭机器人/示教系统API/数据库与配置/脚本执行/步进模式。
  排除条件：仅需原理讲解；参数缺失且无法补齐；请求绕过 token/安全门禁。
---

# 机器人控制 Skill（OpenClaw）

## 1. 目标
将自然语言请求准确映射为：

```bash
python scripts/validate.py <subcommand> [args]
```

并返回统一 JSON：
- 成功：`{"success": true, "command": "...", "result": ...}`
- 失败：`{"success": false, "error": "..."}`

---

## 2. 架构映射（必须遵守）

所有命令按以下链路执行：

1) `scripts/validate.py`：解析 CLI 参数、校验必填项。
2) `scripts/robot_actions.py`：参数类型转换（JSON/float/int）、token 策略。
3) `scripts/robot_core.py`：拼装 HTTP payload，调用具体 API endpoint。

> 规则：除 `init_all` 外，统一使用 namespaced 命令（`action_* / command_* / robot_* / ...`）。

---

## 3. Token / 初始化 / 权限策略

### 3.1 token 规则
- `--token` 可显式传入。
- 未传时：
  - 普通 token 场景：`ensure_token_ready()` 自动申请/复用控制权。
  - 需要初始化就绪的运动场景：`ensure_initialized()` 自动保证初始化完成后再执行。

### 3.2 初始化规则
- 建议先执行：`init_all`。
- 若执行动作命令时机器人未初始化，系统会尝试自动初始化（包含 reset / initialize 流程）。

### 3.3 控制权建议流程
1. `authority_generate --forced 1`（抢占控制权）
2. 执行动作命令
3. 任务结束后 `authority_consume` 释放控制权

---

## 4. 参数规范

### 4.1 必填参数判定
- 以 `validate.py` 中 `required=True` 为准。
- 本 skill 中“必填”均指 CLI 层必填。

### 4.2 复杂参数（JSON 字符串）
下列字段必须传 JSON 字符串（在 actions 层会 `json.loads`）：
- `waypoint`
- `poses`
- `steps`
- `directions`
- `configurations`
- `location_offset`
- 以及其他声明为结构体/数组的参数

示例：
```bash
--steps '[0.0, 0.0, 5.0, 0.0, 0.0, 0.0]'
```

### 4.3 数值参数
- `velocity / acceleration / vel / acc` 等在 actions 层会转 `float`。
- 不能转换时直接报参数错误并终止。

---

## 5. 语义映射（自然语言 -> 命令）

- “打开夹爪” → `action_grip_control --action_type open --value 0`
- “关闭夹爪” → `action_grip_control --action_type close --value 0`
- “夹爪到指定位置” → `action_grip_control --action_type position --value <int>`
- “执行区域动作/perform” → `command_perform --target <target> [--vel --acc --wait]`
- “回安全位” → `command_return_to_safe --target Safe`
- “急停/停机” → `robot_shutdown`
- “停止当前运动” → `robot_stop_motion`
- “相机抓拍” → `action_get_camera_jpg`
- “AGV 去站点” → `action_agv_goto_location --location <name>`

---

## 6. 关键接口编排：步进模式关节运动（重点）

### 6.1 接口说明
- API：`POST /robotControl/setJointsStepping/`
- CLI 命令：`robot_set_joints_stepping`
- 函数映射：
  - `validate.py` 子命令：`robot_set_joints_stepping`
  - `robot_actions.py`：`cmd_robot_set_joints_stepping(args)`
  - `robot_core.py`：`robot_set_joints_stepping(token, steps, velocity, acceleration)`

### 6.2 参数要求（严格）
该接口总计四个参数：
- `token`：脚本编排处理（可不手工输入，系统可自动补齐）
- `steps`：**必填**，JSON（数组）
- `velocity`：**必填**，float
- `acceleration`：**必填**，float

> 用户侧最关键 3 个必填：`steps / velocity / acceleration`。token 按编排策略自动处理。

### 6.3 执行语句模板
```bash
python scripts/validate.py robot_set_joints_stepping \
  --steps '<JSON数组>' \
  --velocity <float> \
  --acceleration <float>
```

### 6.4 示例：设置上装机械臂关节步进目标并开始运动
```bash
python scripts/validate.py robot_set_joints_stepping \
  --steps '[0, 0, 3.5, 0, 0, 0]' \
  --velocity 20 \
  --acceleration 20
```

### 6.5 执行前置检查（必须）
1. 人员已离开危险区域。
2. 机械臂轨迹无遮挡、无碰撞风险。
3. 急停按钮可达且可用。
4. 已获得用户“允许真实执行”确认。

若任一项不满足：**禁止执行**，仅返回风险说明与补救建议。

### 6.6 执行后控制（建议）
- 连续步进微调场景：配合 `robot_keep_joints_tuning_alive` 保活，结束后 `robot_stop_joints_tuning`。
- 若异常：优先 `robot_stop_motion`，必要时 `robot_shutdown`。

---

## 7. 常用命令分组与参数（精简版）

### 7.1 初始化与权限
- `init_all`：一键初始化（兼容入口）
- `authority_generate [--forced]`
- `authority_consume`
- `authority_is_accessible`
- `authority_is_controller`
- `authority_seize [--forced]`

### 7.2 动作控制（action_*）
- `action_grip_control --action_type --value`
- `action_peripheral_control --peripheral --action_type --value`
- `action_agv_goto_location --location`
- `action_agv_load_map --map_name`
- `action_vehicle_move --position --velocity`
- `action_get_camera_jpg`

### 7.3 任务命令（command_*）
- `command_perform --target [--vel --acc --wait]`
- `command_pick --target [--consumable --vel --acc --wait --covered]`
- `command_place --target [--consumable --vel --acc --wait --covered]`
- `command_transfer --source --target [--consumable --vel --acc --wait --covered]`
- `command_return_to_safe --target`

### 7.4 机械臂控制（robot_*）
- `robot_set_joints_stepping --steps --velocity --acceleration`
- `robot_set_joints_tuning --directions --velocity --acceleration`
- `robot_set_pose_stepping --steps --velocity --acceleration`
- `robot_set_motion --waypoint --motion --vel --acc`
- `robot_stop_motion`
- `robot_shutdown`

---

## 8. 安全门禁（强制）

以下命令属于“真实运动/状态改变”，执行前必须满足安全门禁：
- 全部 `robot_*`（含运动、停机）
- 多数 `action_*`（夹爪、AGV、vehicle、外围设备）
- 多数 `command_*`
- 操作型 `script_api_*`

门禁清单：
1. 危险区域无人；
2. 路径无障碍；
3. 急停可达；
4. 用户明确授权执行。

未确认时只做说明，不执行。

---

## 9. 失败处理与回退

- 参数缺失：列出缺失字段并提供可执行模板。
- JSON 解析失败：指出具体字段（如 `steps`）与示例格式。
- 网络失败：返回网络错误，建议重试并检查机器人服务连通性。
- 业务失败：原样回传业务错误信息；必要时建议先 `init_all` 或重新申请 token。

---

## 10. 推荐执行流程（模板）

1. 收集目标命令与必填参数。
2. 进行安全门禁确认。
3. 生成 CLI 命令并执行。
4. 返回标准 JSON 结果。
5. 若为调试/连续控制，补充 stop/释放控制权建议。
