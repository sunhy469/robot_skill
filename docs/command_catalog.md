# 命令清单（详细版）

> 本文专门解决“自然语言语义 -> CLI 命令”的映射歧义。所有示例都以 `python scripts/validate.py` 为统一入口。

## 0. 一条总规则（先读）

- 只要用户明确说“执行一个 **perform**”，一律优先映射为 `command_perform`。
- 只有用户明确说“pick / place / transfer”或明确表达“抓取/放置/转运流程命令”时，才映射到 `command_pick / command_place / command_transfer`。
- “向前移动”若语境是“下装 AGV / 下装工具底盘”，默认是 AGV 直线平移 `action_agv_translate`，**不是**机械臂 `robot_set_pose_stepping`。

---

## 1. 高频语义映射（自然语言 -> 命令）

### 1.1 Perform / Pick / Place 的优先级（重点）

| 用户表达 | 正确映射 | 说明 |
|---|---|---|
| 执行一个取耗材的 perform | `command_perform --target 取耗材` | 关键在“perform”这个词，不要误映射成 `command_pick` |
| 执行一个放耗材的 perform | `command_perform --target 放耗材` | 同理，不要误映射成 `command_place` |
| 执行 test_area_01 的 perform | `command_perform --target test_area_01` | 目标区域/动作名填入 `target` |
| 抓取耗材 / pick 耗材 | `command_pick --target <区域> [--consumable ...]` | 用户语义明确是 pick 流程 |
| 放置耗材 / place 耗材 | `command_place --target <区域> [--consumable ...]` | 用户语义明确是 place 流程 |
| 从 A 转运到 B | `command_transfer --source A --target B ...` | 明确是转运流程 |

### 1.2 AGV 与机械臂的“向前移动”消歧（重点）

| 用户表达 | 默认映射 | 为什么 |
|---|---|---|
| 下装 AGV 向前移动 10cm | `action_agv_translate --dist 0.1 --vx 0.05 --vy 0.0 --mode 0` | 语义主语是 AGV 底盘 |
| 下装工具向前移动 | `action_agv_translate --dist <米>` | 同上，属于底盘运动 |
| 机械臂末端向前移动 5cm | `robot_set_pose_stepping --steps '[-0.05,0,0,[0,0,0]]' ...` | 主语是机械臂末端，属于笛卡尔步进 |

> 坐标提醒：在当前约定中，机械臂 X 负方向是“向前”；AGV 的 `dist` 为正表示按当前朝向前进。

### 1.3 其他高频语义

- “打开夹爪” -> `action_grip_control --action_type Open --value 0`
- “关闭夹爪” -> `action_grip_control --action_type Close --value 0`
- “回安全位” -> `command_return_to_safe --target Safe`
- “停止当前运动” -> `robot_stop_motion`
- “急停/停机” -> `robot_shutdown`
- “相机抓拍” -> `action_get_camera_jpg`
- “识别板位是否有耗材” -> `action_detect_consumable`

---

## 2. 关键命令示例（可直接复用）

## 2.1 Perform 类

### 执行一个“取耗材”的 perform（不是 pick）

```bash
python scripts/validate.py command_perform \
  --target 取耗材 \
  --vel 30 \
  --acc 30 \
  --wait 1
```

### 执行一个“放耗材”的 perform（不是 place）

```bash
python scripts/validate.py command_perform \
  --target 放耗材 \
  --vel 30 \
  --acc 30 \
  --wait 1
```

### 执行指定区域动作 perform

```bash
python scripts/validate.py command_perform \
  --target test_area_01 \
  --vel 20 \
  --acc 20 \
  --wait 1
```

## 2.2 AGV 类

### 下装 AGV 向前移动 10cm

```bash
python scripts/validate.py action_agv_translate \
  --dist 0.1 \
  --vx 0.05 \
  --vy 0.0 \
  --mode 0
```

### AGV 原地左转（逆时针）

```bash
python scripts/validate.py action_agv_turn \
  --angle 3.14 \
  --vw 1.6 \
  --mode 0
```

### AGV 原地右转（顺时针）

```bash
python scripts/validate.py action_agv_turn \
  --angle 3.14 \
  --vw -1.6 \
  --mode 0
```

---

## 3. 全量命令分组（索引）

## 3.1 初始化与权限

- `init_all`
- `authority_generate [--forced]`
- `authority_consume`
- `authority_is_accessible`
- `authority_is_controller`
- `authority_seize [--forced]`

## 3.2 动作控制（action_*）

- `action_grip_control --action_type --value`
- `action_peripheral_control --peripheral --action_type --value`
- `action_agv_goto_location --location`
- `action_agv_load_map --map_name`
- `action_agv_translate --dist [--vx --vy --mode --ip --port]`
- `action_agv_turn --angle --vw [--mode --ip --port]`
- `action_vehicle_move --position --velocity`
- `action_get_camera_jpg`
- `action_detect_consumable`

## 3.3 任务命令（command_*）

- `command_perform --target [--vel --acc --wait]`
- `command_pick --target [--consumable --vel --acc --wait --covered]`
- `command_place --target [--consumable --vel --acc --wait --covered]`
- `command_transfer --source --target [--consumable --vel --acc --wait --covered]`
- `command_return_to_safe --target`

## 3.4 机械臂（robot_*）

- `robot_set_joints_stepping --steps --velocity --acceleration`
- `robot_set_joints_tuning --directions --velocity --acceleration`
- `robot_set_pose_stepping --steps --velocity --acceleration`
- `robot_set_motion --waypoint --motion --vel --acc`
- `robot_stop_motion`
- `robot_shutdown`

---

## 4. 常见误映射与纠正

- 误：用户说“执行一个取耗材 perform”，却执行 `command_pick`。
  - 正：`command_perform --target 取耗材`
- 误：用户说“执行一个放耗材 perform”，却执行 `command_place`。
  - 正：`command_perform --target 放耗材`
- 误：用户说“下装 AGV 向前移动”，却执行机械臂 `robot_set_pose_stepping`。
  - 正：`action_agv_translate --dist <正数>`

