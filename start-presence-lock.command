#!/bin/bash
# presence-lock 一键启动：双击本文件即运行
# 关闭此终端窗口即停止
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

if [ ! -f "known_faces.npy" ]; then
    echo "================================================"
    echo "  还没注册你的脸。"
    echo "  先运行一次：./run.sh register.py"
    echo "================================================"
    exit 1
fi

echo "================================================"
echo "  PresenceLock 在场检测锁屏"
echo "================================================"
echo ""
echo "  摄像头确认本人在电脑前，人不在自动锁屏"
echo "  关闭此窗口即停止运行"
echo ""
echo "  正在启动..."
echo ""

exec ./run.sh main.py
