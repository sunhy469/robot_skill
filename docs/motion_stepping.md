# 步进运动（Pose / Joints）

## A. 笛卡尔步进：`robot_set_pose_stepping`

### 参数
- `--steps` 必填，JSON：`[x, y, z, [rx, ry, rz]]`
- `--velocity` 必填，float
- `--acceleration` 必填，float

### 坐标方向
- X：负向前，正向后
- Y：正向右，负向左
- Z：正向上，负向下


### 模板
```bash
python scripts/validate.py robot_set_pose_stepping \
  --steps '[x, y, z, [rx, ry, rz]]' \
  --velocity <float> \
  --acceleration <float>
```

## 工具姿态调整（旋转运动）

### 说明
`steps` 参数的旋转部分 `[rx, ry, rz]` 用于控制工具（机械臂头部/末端执行器）的姿态调整，**不影响整体位置**。
- `rx`：绕 X 轴旋转（右倾/左倾）
- `ry`：绕 Y 轴旋转（抬头/低头）
- `rz`：绕 Z 轴旋转（右旋/左旋）

### 常用姿态调整示例

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

### 旋转轴方向总结
| 动作 | 参数 | 说明 |
|------|------|------|
| 右旋 | `[0, 0, -角度]` | 绕 Z 轴负方向旋转 |
| 左旋 | `[0, 0, +角度]` | 绕 Z 轴正方向旋转 |
| 抬头 | `[0, +角度，0]` | 绕 Y 轴正方向旋转 |
| 低头 | `[0, -角度，0]` | 绕 Y 轴负方向旋转 |
| 右倾 | `[-角度，0, 0]` | 绕 X 轴负方向旋转 |
| 左倾 | `[+角度，0, 0]` | 绕 X 轴正方向旋转 |



## C. 执行前置检查（必须）

1. 人员离开危险区域
2. 轨迹无遮挡且无碰撞风险
3. 急停可达且可用
4. 用户明确授权执行
