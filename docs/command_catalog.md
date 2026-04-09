# 命令清单（精简）

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
- `command_perform --target [--vel --acc --wait]`
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
