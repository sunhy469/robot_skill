# 命令清单（精简）

## 语义映射（自然语言 -> 命令）
- “识别板位是否有耗材” → `action_detect_consumable`（内部固定执行 `perform(target=移动到拍摄位置)`，抓拍后默认对比 `references/current_view.jpg` 与 `references/true_view.jpg`）
- “下裝工具向前移动” → `action_agv_translate --dist 0.1`（默认带 `vx=0.05 vy=0.0 mode=0`，可按需覆盖）
- “AGV 原地向左转动/左转” → `action_agv_turn --angle 3.14 --vw 1.6`（可选 `--mode`，默认 `mode=0`）
- “AGV 原地向右转动/右转” → `action_agv_turn --angle 3.14 --vw -1.6`（可选 `--mode`，默认 `mode=0`）

## 初始化与权限
- `init_all`
- `authority_generate [--forced]`
- `authority_consume`
- `authority_is_accessible`
- `authority_is_controller`
- `authority_seize [--forced]`

## 动作控制（action_*）
- `action_grip_control --action_type --value`
- `action_peripheral_control --peripheral --action_type --value`
- `action_agv_goto_location --location`
- `action_agv_load_map --map_name`
- `action_vehicle_move --position --velocity`
- `action_get_camera_jpg`

## 任务命令（command_*）
- “执行一个perform,放耗材/test_area_01” → `command_perform --target [--vel --acc --wait]`
- `command_pick --target [--consumable --vel --acc --wait --covered]`
- `command_place --target [--consumable --vel --acc --wait --covered]`
- `command_transfer --source --target [--consumable --vel --acc --wait --covered]`
- `command_return_to_safe --target`

## 机械臂（robot_*）
- `robot_set_joints_stepping --steps --velocity --acceleration`
- `robot_set_joints_tuning --directions --velocity --acceleration`
- `robot_set_pose_stepping --steps --velocity --acceleration`
- `robot_set_motion --waypoint --motion --vel --acc`
- `robot_stop_motion`
- `robot_shutdown`


