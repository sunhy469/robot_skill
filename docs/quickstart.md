# 快速开始与执行编排

## 1) 核心命令格式

```bash
python scripts/validate.py <subcommand> [args]
```

## 2) 推荐执行顺序

1. `init_all`（建议先执行）
2. `authority_generate --forced 1`（抢占控制权）
3. 执行动作命令
4. `authority_consume`（任务结束释放控制权）

## 3) token 行为

- 可显式传 `--token`
- 未传时由 actions 层自动补齐：
  - 普通命令：`ensure_token_ready()`
  - 运动命令：`ensure_initialized()`

## 4) 统一输出

- 成功：`{"success": true, "command": "...", "result": ...}`
- 失败：`{"success": false, "error": "..."}`

## 5) 执行前语义确认（建议每次都做）

- 若用户说“执行一个 xxx perform”，按 `command_perform --target xxx`。
- 若用户说“下装 AGV 向前移动”，按 `action_agv_translate`，不要误用机械臂命令。
- 若用户说“机械臂末端向前/后/上/下/姿态调整”，按 `robot_set_pose_stepping`。

> 可直接对照 `docs/command_catalog.md` 的“语义映射”章节，先消歧再执行。

