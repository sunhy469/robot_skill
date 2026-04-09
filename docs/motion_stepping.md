# 步进运动（Pose / Joints）

## A. 笛卡尔步进：`robot_set_pose_stepping`

### 参数
- `--steps` 必填，JSON：`[x, y, z, [rx, ry, rz]]`
- `--velocity` 必填，float
- `--acceleration` 必填，float

### 模板
```bash
python scripts/validate.py robot_set_pose_stepping \
  --steps '[x, y, z, [rx, ry, rz]]' \
  --velocity <float> \
  --acceleration <float>
```

### 坐标方向
- X：负向前，正向后
- Y：正向右，负向左
- Z：正向上，负向下

### 常用示例
```bash
# 上移 10cm
python scripts/validate.py robot_set_pose_stepping --steps '[0,0,0.1,[0,0,0]]' --velocity 50 --acceleration 50

# 下移 10cm
python scripts/validate.py robot_set_pose_stepping --steps '[0,0,-0.1,[0,0,0]]' --velocity 50 --acceleration 50

# 工具右旋 0.5°（绕 Z 轴负向）
python scripts/validate.py robot_set_pose_stepping --steps '[0,0,0,[0,0,-0.5]]' --velocity 30 --acceleration 30
```

---

## B. 关节步进：`robot_set_joints_stepping`

### 参数
- `--steps` 必填，JSON：`[j1, j2, j3, j4, j5, j6]`
- `--velocity` 必填，float
- `--acceleration` 必填，float

### 模板
```bash
python scripts/validate.py robot_set_joints_stepping \
  --steps '[j1, j2, j3, j4, j5, j6]' \
  --velocity <float> \
  --acceleration <float>
```

### 常用示例
```bash
# 第3关节 +5°
python scripts/validate.py robot_set_joints_stepping --steps '[0,0,5,0,0,0]' --velocity 50 --acceleration 50

# 全关节微调 +1°
python scripts/validate.py robot_set_joints_stepping --steps '[1,1,1,1,1,1]' --velocity 30 --acceleration 30
```

---

## C. 执行前置检查（必须）

1. 人员离开危险区域
2. 轨迹无遮挡且无碰撞风险
3. 急停可达且可用
4. 用户明确授权执行
