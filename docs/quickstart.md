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
