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
- “下裝工具向前移动” → `action_agv_translate --dist 0.1`（默认带 `vx=0.05 vy=0.0 mode=0`，可按需覆盖）
- “AGV 原地转动/旋转” → `action_agv_turn --angle <rad> --vw <rad/s>`（可选 `--mode`，默认 `mode=0`）
- “打开夹爪” → `action_grip_control --action_type Open --value 0`
- “关闭夹爪” → `action_grip_control --action_type Close --value 0`
- “夹爪到指定位置” → `action_grip_control --action_type Position --value <int>`
- “执行区域动作/perform” → `command_perform --target <target> [--vel --acc --wait]`
- “回安全位” → `command_return_to_safe --target Safe`
- “急停/停机” → `robot_shutdown`
- “停止当前运动” → `robot_stop_motion`
- “相机抓拍” → `action_get_camera_jpg`
- “识别板位是否有耗材” → `action_detect_consumable`（内部固定执行 `perform(target=移动到拍摄位置)`，抓拍后默认对比 `references/current_view.jpg` 与 `references/true_view.jpg`）
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

## 6. 关键接口编排：笛卡尔坐标步进运动（重点）

### 6.1 接口说明
- API：`POST /robotControl/setPoseStepping/`
- CLI 命令：`robot_set_pose_stepping`
- 函数映射：
  - `validate.py` 子命令：`robot_set_pose_stepping`
  - `robot_actions.py`：`cmd_robot_set_pose_stepping(args)`
  - `robot_core.py`：`robot_set_pose_stepping(token, steps, velocity, acceleration)`

### 6.2 参数要求（严格）
该接口总计四个参数：
- `token`：脚本编排处理（可不手工输入，系统可自动补齐）
- `steps`：**必填**，JSON（数组），格式：`[x, y, z, [rx, ry, rz]]`
  - `x, y, z`：笛卡尔坐标位移（单位：米）
  - `[rx, ry, rz]`：欧拉角旋转（单位：度）
- `velocity`：**必填**，float
- `acceleration`：**必填**，float

### 6.3 执行语句模板
```bash
python scripts/validate.py robot_set_pose_stepping \
  --steps '[x, y, z, [rx, ry, rz]]' \
  --velocity <float> \
  --acceleration <float>
```

### 6.4 常用移动示例

#### 向上移动 10cm（Z 轴 +0.1 米）
```bash
python scripts/validate.py robot_set_pose_stepping \
  --steps '[0, 0, 0.1, [0, 0, 0]]' \
  --velocity 50 \
  --acceleration 50
```

#### 向下移动 10cm（Z 轴 -0.1 米）
```bash
python scripts/validate.py robot_set_pose_stepping \
  --steps '[0, 0, -0.1, [0, 0, 0]]' \
  --velocity 50 \
  --acceleration 50
```

#### 向前移动 5cm（X 轴 -0.05 米）
```bash
python scripts/validate.py robot_set_pose_stepping \
  --steps '[-0.05, 0, 0, [0, 0, 0]]' \
  --velocity 50 \
  --acceleration 50
```

#### 向后移动 5cm（X 轴 +0.05 米）
```bash
python scripts/validate.py robot_set_pose_stepping \
  --steps '[0.05, 0, 0, [0, 0, 0]]' \
  --velocity 50 \
  --acceleration 50
```

#### 向右移动 5cm（Y 轴 +0.05 米）
```bash
python scripts/validate.py robot_set_pose_stepping \
  --steps '[0, 0.05, 0, [0, 0, 0]]' \
  --velocity 50 \
  --acceleration 50
```

#### 向左移动 5cm（Y 轴 -0.05 米）
```bash
python scripts/validate.py robot_set_pose_stepping \
  --steps '[0, -0.05, 0, [0, 0, 0]]' \
  --velocity 50 \
  --acceleration 50
```

#### 绕 Z 轴旋转 90 度
```bash
python scripts/validate.py robot_set_pose_stepping \
  --steps '[0, 0, 0, [0, 0, 90]]' \
  --velocity 50 \
  --acceleration 50
```

### 6.4.1 坐标轴方向说明
根据实际测试，该机械臂的坐标轴定义如下：
- **X 轴**：负方向为前，正方向为后
- **Y 轴**：正方向为右，负方向为左
- **Z 轴**：正方向为上，负方向为下

---

## 6.5 工具姿态调整（旋转运动）

### 6.5.1 说明
`steps` 参数的旋转部分 `[rx, ry, rz]` 用于控制工具（机械臂头部/末端执行器）的姿态调整，**不影响整体位置**。
- `rx`：绕 X 轴旋转（右倾/左倾）
- `ry`：绕 Y 轴旋转（抬头/低头）
- `rz`：绕 Z 轴旋转（右旋/左旋）

### 6.5.2 常用姿态调整示例

#### 右旋 0.5 度（绕 Z 轴负方向）
```bash
python scripts/validate.py robot_set_pose_stepping \
  --steps '[0, 0, 0, [0, 0, -0.5]]' \
  --velocity 30 \
  --acceleration 30
```

#### 左旋 0.5 度（绕 Z 轴正方向）
```bash
python scripts/validate.py robot_set_pose_stepping \
  --steps '[0, 0, 0, [0, 0, 0.5]]' \
  --velocity 30 \
  --acceleration 30
```

#### 抬头 0.5 度（绕 Y 轴正方向）
```bash
python scripts/validate.py robot_set_pose_stepping \
  --steps '[0, 0, 0, [0, 0.5, 0]]' \
  --velocity 30 \
  --acceleration 30
```

#### 低头 0.5 度（绕 Y 轴负方向）
```bash
python scripts/validate.py robot_set_pose_stepping \
  --steps '[0, 0, 0, [0, -0.5, 0]]' \
  --velocity 30 \
  --acceleration 30
```

#### 右倾 0.5 度（绕 X 轴负方向）
```bash
python scripts/validate.py robot_set_pose_stepping \
  --steps '[0, 0, 0, [-0.5, 0, 0]]' \
  --velocity 30 \
  --acceleration 30
```

#### 左倾 0.5 度（绕 X 轴正方向）
```bash
python scripts/validate.py robot_set_pose_stepping \
  --steps '[0, 0, 0, [0.5, 0, 0]]' \
  --velocity 30 \
  --acceleration 30
```

### 6.5.3 旋转轴方向总结
| 动作 | 参数 | 说明 |
|------|------|------|
| 右旋 | `[0, 0, -角度]` | 绕 Z 轴负方向旋转 |
| 左旋 | `[0, 0, +角度]` | 绕 Z 轴正方向旋转 |
| 抬头 | `[0, +角度，0]` | 绕 Y 轴正方向旋转 |
| 低头 | `[0, -角度，0]` | 绕 Y 轴负方向旋转 |
| 右倾 | `[-角度，0, 0]` | 绕 X 轴负方向旋转 |
| 左倾 | `[+角度，0, 0]` | 绕 X 轴正方向旋转 |

### 6.5.4 注意事项
- 旋转角度单位为**度**（degrees）
- 姿态调整仅改变工具朝向，不改变末端执行器的位置
- 建议速度设为较低值（如 30），以保证精度
- 可以结合位置移动和姿态调整一起使用，例如：`[-0.1, 0, -0.1, [0, 5, 0]]` 表示向前 10cm、向下 10cm、同时抬头 5 度

### 6.5 执行前置检查（必须）
1. 人员已离开危险区域。
2. 机械臂轨迹无遮挡、无碰撞风险。
3. 急停按钮可达且可用。
4. 已获得用户“允许真实执行”确认。

若任一项不满足：**禁止执行**，仅返回风险说明与补救建议。

---

## 7. 关键接口编排：关节角度步进运动

### 7.1 接口说明
- API：`POST /robotControl/setJointsStepping/`
- CLI 命令：`robot_set_joints_stepping`
- 函数映射：
  - `validate.py` 子命令：`robot_set_joints_stepping`
  - `robot_actions.py`：`cmd_robot_set_joints_stepping(args)`
  - `robot_core.py`：`robot_set_joints_stepping(token, steps, velocity, acceleration)`

### 7.2 参数要求（严格）
该接口总计四个参数：
- `token`：脚本编排处理（可不手工输入，系统可自动补齐）
- `steps`：**必填**，JSON（数组），格式：`[j1, j2, j3, j4, j5, j6]`
  - `j1-j6`：6 个关节的角度变化量（单位：度）
- `velocity`：**必填**，float
- `acceleration`：**必填**，float

### 7.3 执行语句模板
```bash
python scripts/validate.py robot_set_joints_stepping \
  --steps '[j1, j2, j3, j4, j5, j6]' \
  --velocity <float> \
  --acceleration <float>
```

### 7.4 常用移动示例

#### 仅第 3 个关节旋转 5 度
```bash
python scripts/validate.py robot_set_joints_stepping \
  --steps '[0, 0, 5, 0, 0, 0]' \
  --velocity 50 \
  --acceleration 50
```

#### 第 1、2 关节各旋转 10 度
```bash
python scripts/validate.py robot_set_joints_stepping \
  --steps '[10, 10, 0, 0, 0, 0]' \
  --velocity 50 \
  --acceleration 50
```

# 8. 区域流程管理 (Area Workflow Management)

## 8.1 概述

区域流程管理用于创建和管理机器人的 perform 任务流程。一个完整的流程包括：
- **创建区域**：定义新的工作区域
- **保存位姿**：将机械臂的不同位置保存为 Pose
- **更新流程**：配置每个 Pose 的动作和参数
- **执行任务**：通过 `command_perform` 执行完整的流程

## 8.2 可用 Pose 类型

```python
Base, Turn, Out, Prepare, On, OnPick, OnPlace, Safe, Middle,
UpPoint, DownPoint, ToolBase, ToolTurn, ToolOut, ToolPrepare,
ToolOn, ToolOnPick, ToolOnPlace, GripBase, GripTurn, GripOut,
GripPrepare, GripOn, GripOnPick, GripOnPlace
```

## 8.3 创建新区域

### 接口说明
- **命令**: `new_area`
- **作用**: 创建一个新的工作区域，默认包含 Base、On、Prepare 三个 Pose

### 参数要求
- `--name`: **必填**, 区域名称（如 "材料移动"）
- `--area_type`: 可选，默认 "fixed"
- `--tag_area`: 可选，默认 ""
- `--eoat`: 可选，默认 "DEFAULT"
- `--offset_z`: 可选，默认 0
- `--pose`: 可选，JSON 数组，默认 ["Base", "On", "Prepare"]
- `--rotation`: 可选，默认 "Forward0"
- `--teach_plate_inside_z`: 可选，默认 0
- `--type_`: 可选，默认 "Normal"
- `--upland_z`: 可选，默认 0

### 执行语句模板
```bash
python scripts/validate.py new_area \
  --name "材料移动" \
  --area_type "fixed" \
  --eoat "DEFAULT" \
  --pose '["Base", "On", "Prepare"]'
```

### 示例：创建名为"材料移动"的区域
```bash
python scripts/validate.py new_area --name "材料移动"
```

## 8.4 获取当前位姿

### 接口说明
- **命令**: `get_current_waypoint`
- **作用**: 获取机械臂当前的位姿信息

### 执行语句模板
```bash
python scripts/validate.py get_current_waypoint
```

### 返回示例
```json
{
  "success": true,
  "result": {
    "waypoint": {
      "joint": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
      "pose": [0.5, 0.3, 0.2, 0, 0, 0]
    }
  }
}
```

## 8.5 保存位姿到 Pose

### 接口说明
- **命令**: `save_waypoint`
- **作用**: 将当前位姿保存到指定区域的指定 Pose

### 参数要求
- `--waypoint`: **必填**, JSON 格式，从 `get_current_waypoint` 获取
- `--area_name`: **必填**, 区域名称
- `--pose`: **必填**, Pose 名称（如 Base、Turn 等）

### 执行语句模板
```bash
python scripts/validate.py save_waypoint \
  --waypoint '{...}' \
  --area_name "材料移动" \
  --pose "Base"
```

### 完整流程示例
```bash
# 1. 移动到目标位置
python scripts/validate.py robot_set_pose_stepping --steps '[0, 0, -0.1, [0, 0, 0]]'

# 2. 获取当前位姿
WAYPOINT=$(python scripts/validate.py get_current_waypoint | jq '.result.waypoint')

# 3. 保存为 Base Pose
python scripts/validate.py save_waypoint \
  --waypoint "$WAYPOINT" \
  --area_name "材料移动" \
  --pose "Base"
```

## 8.6 获取区域流程信息

### 接口说明
- **命令**: `get_areas_process`
- **作用**: 获取指定区域的完整流程信息

### 参数要求
- `--area_name`: **必填**, 区域名称
- `--process_type`: 可选，默认 "Work"

### 执行语句模板
```bash
python scripts/validate.py get_areas_process \
  --area_name "材料移动" \
  --process_type "Work"
```

### 返回示例
```json
{
  "success": true,
  "data": {
    "Process": [
      {
        "Pose": "Base",
        "MotionType": "JMove",
        "VelRate": 50,
        "AccRate": 50,
        "ActionType": "Other",
        "ActionPara": "Inaction"
      },
      {
        "Pose": "Turn",
        "MotionType": "JMove",
        "VelRate": 50,
        "AccRate": 50,
        "ActionType": "Gripper",
        "ActionPara": "Close"
      }
    ]
  }
}
```

## 8.7 更新区域流程

### 接口说明
- **命令**: `update_process`
- **作用**: 更新区域的完整流程配置

### 参数要求
- `--area_name`: **必填**, 区域名称
- `--process_list`: **必填**, JSON 数组，包含所有 Pose 的配置
- `--process_type`: 可选，默认 "Work"

### Process 对象字段说明
```json
{
  "Pose": "Base",           # Pose 名称
  "MotionType": "JMove",    # 运动类型：JMove(关节), LMove(直线)
  "ProcessId": 0,           # 流程 ID（从 0 开始）
  "NextProcessId": 1,       # 下一个流程 ID
  "VelRate": 50,            # 速度百分比
  "AccRate": 50,            # 加速度百分比
  "ActionType": "Other",    # 动作类型：Other, Gripper
  "ActionPara": "Inaction", # 动作参数：Inaction, Close, Open
  "Grasp": 0,               # 夹爪状态：0=无，1=关闭，2=打开
  "Switch": 1,              # 是否启用：0=禁用，1=启用
  "IsOffset": 0             # 是否偏移：0=否，1=是
}
```

### 执行语句模板
```bash
python scripts/validate.py update_process \
  --area_name "材料移动" \
  --process_list '[{"Pose":"Base","MotionType":"JMove","ProcessId":0,"NextProcessId":1,"VelRate":50,"AccRate":50,"ActionType":"Other","ActionPara":"Inaction","Grasp":0,"Switch":1,"IsOffset":0},{"Pose":"Turn","MotionType":"JMove","ProcessId":1,"NextProcessId":2,"VelRate":50,"AccRate":50,"ActionType":"Gripper","ActionPara":"Close","Grasp":1,"Switch":1,"IsOffset":0}]' \
  --process_type "Work"
```

## 8.8 删除指定 Pose

### 接口说明
- **命令**: `delete_pose`
- **作用**: 从区域流程中删除指定的 Pose

### 参数要求
- `--area_name`: **必填**, 区域名称
- `--pose`: **必填**, 要删除的 Pose 名称
- `--process_type`: 可选，默认 "Work"

### 执行语句模板
```bash
python scripts/validate.py delete_pose \
  --area_name "材料移动" \
  --pose "Prepare"
```

## 8.9 完整工作流程示例

### 场景：创建"材料移动"任务

```bash
# 步骤 1: 创建新区域
python scripts/validate.py new_area --name "材料移动"

# 步骤 2: 移动到 Base 位置并保存
python scripts/validate.py robot_set_pose_stepping --steps '[0.1, 0, 0.2, [0, 0, 0]]'
WAYPOINT_BASE=$(python scripts/validate.py get_current_waypoint)
python scripts/validate.py save_waypoint --waypoint "$WAYPOINT_BASE" --area_name "材料移动" --pose "Base"

# 步骤 3: 移动到 Turn 位置并保存
python scripts/validate.py robot_set_pose_stepping --steps '[-0.05, 0, 0, [0, 0, 0.5]]'
WAYPOINT_TURN=$(python scripts/validate.py get_current_waypoint)
python scripts/validate.py save_waypoint --waypoint "$WAYPOINT_TURN" --area_name "材料移动" --pose "Turn"

# 步骤 4: 移动到 On 位置并保存
python scripts/validate.py robot_set_pose_stepping --steps '[0, -0.1, -0.1, [0, 0, 0]]'
WAYPOINT_ON=$(python scripts/validate.py get_current_waypoint)
python scripts/validate.py save_waypoint --waypoint "$WAYPOINT_ON" --area_name "材料移动" --pose "On"

# 步骤 5: 查看流程信息
python scripts/validate.py get_areas_process --area_name "材料移动"

# 步骤 6: 执行任务
python scripts/validate.py command_perform --target "材料移动"
```

## 8.10 使用辅助脚本

为了方便管理，提供了示例脚本 `area_workflow_example.py`：

```bash
# 运行示例脚本
python scripts/area_workflow_example.py

# 或在 Python 中使用
from scripts.area_workflow_example import *
token = generate_token()
save_pose_to_area(token, "材料移动", "Base")
```

# 9. 故障排查

## 9.1 常见问题
```bash
python scripts/validate.py robot_set_joints_stepping \
  --steps '[10, 10, 0, 0, 0, 0]' \
  --velocity 50 \
  --acceleration 50
```

#### 所有关节微调（各 1 度）
```bash
python scripts/validate.py robot_set_joints_stepping \
  --steps '[1, 1, 1, 1, 1, 1]' \
  --velocity 30 \
  --acceleration 30
```

### 7.5 注意事项
- 关节角度步进运动控制的是每个关节的相对角度变化
- 对于末端执行器的笛卡尔位移，建议使用 `robot_set_pose_stepping`
- 关节角度步进适合精细调整和特定姿态控制

---

## 8. 常用命令分组与参数（精简版）

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
