# presence-lock

macOS 摄像头在场检测锁屏工具：确认电脑前的人是**你**，不是任何人。

别人坐到你电脑前（或你离开超过设定时间），自动锁屏。

## 原理

- 摄像头读帧 → macOS 原生 Vision 框架（VNCreateFaceprintRequest）检测人脸并生成 128 维特征
- 第一次使用时注册你的脸（`register.py`），之后每帧比对：是本人 → 安全；没人 / 非本人 → 计时 → 锁屏
- 锁屏用 `pmset displaysleepnow` 关闭显示器，唤醒需要密码（零权限，最可靠）
- 摄像头不是一直开：待机时关闭（绿灯灭），键鼠空闲超阈值或每 5 分钟才启动一次确认

## 安装

```bash
cd /Users/qinbai/Documents/个人项目/presence-lock
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 使用

所有命令用 `./run.sh` 启动（它清掉宿主环境的 PYTHONPATH，防止 import 串环境）：

```bash
# 1. 注册你的脸（首次会弹摄像头权限，点允许）
./run.sh register.py
#    按 s 拍 3 张（正面/稍侧/稍抬头），按 q 保存

# 2. 先试 dry-run：只检测不锁屏，看识别准不准
./run.sh main.py --dry-run --preview

# 3. 正式运行
./run.sh main.py
```

### 一键启动（日常使用）

双击 `start-presence-lock.command` 启动（弹出终端窗口显示状态，关闭窗口即停止）。
双击 `stop-presence-lock.command` 停止。

## 权限（只申请一次）

| 权限 | 位置 | 用途 |
|---|---|---|
| 摄像头 | 首次运行弹窗，点允许 | 读摄像头 |

锁屏不需要额外权限，但必须确认系统设置里开了「屏幕关闭后要求密码」：
系统设置 > 锁定屏幕 > 屏幕关闭后要求密码 > 立即（或短延迟）。
否则关屏唤醒不需要密码，等于没锁。

## 配置（config.json）

| 参数 | 默认 | 含义 |
|---|---|---|
| idle_threshold_sec | 10 | 键鼠空闲多久后启动摄像头确认 |
| idle_grace_sec | 30 | 确认过本人后，空闲多久才需要再次摄像头确认 |
| absent_lock_sec | 10 | 确认阶段连续多久没检测到本人就锁屏 |
| alert_sec | 3 | 锁屏前倒计时（秒），期间人回来看摄像头可取消 |
| recheck_interval_sec | 300 | 每 5 分钟强制复查一次，防陌生人坐过来 |
| match_threshold | 0.60 | 人脸比对距离阈值，越小越严格（认错人调低，误锁调高） |
| frame_interval_sec | 1.0 | 检测帧间隔（秒） |

## 已知限制（诚实说明）

1. 摄像头绿灯常亮是硬件行为，软件关不掉。本工具尽量只在确认阶段开摄像头，正常使用时每 5 分钟亮几秒。
2. 本人低头、背对屏幕超过 absent_lock_sec 会被锁（罕见）。倒计时 3 秒内看摄像头可取消。
3. 这个工具防不住你把密码告诉别人。锁屏防线是系统锁屏，够用但不万能。
4. 锁屏（关屏）后 60 秒内不检测（等唤醒），之后回到待机。

## 踩坑记录（写给以后的自己）

- 锁屏不能走 osascript 模拟 Cmd+Ctrl+Q（error 1002，TCC 查 osascript 自身）也不能走
  CGEventPost（macOS 15 静默丢弃无权限 CLI 注入的事件），CGSession 工具已被移除。
  pmset displaysleepnow 零权限可用，配合「屏幕关闭后要求密码」设置。
- pyobjc 的 Vision 绑定没有 VNGenerateFaceEmbeddingsRequest（macOS 14 新 API），
  用 VNCreateFaceprintRequest + obs.faceprint().descriptorData()（128 维 float32）。
- Hermes 等宿主环境会注入 PYTHONPATH，venv 里 import 会串到宿主 numpy（版本不匹配崩）。
  用 `env -u PYTHONPATH` 或 run.sh 启动。
- 摄像头权限：OpenCV 请求权限后不等人点允许就失败。先用 swiftc 编译的 grant_camera_bin
  请求权限（弹窗等用户点），再跑 OpenCV。
