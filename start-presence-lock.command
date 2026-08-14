#!/bin/bash
# presence-lock 一键启动：双击本文件，程序在后台运行
# 终端窗口可以立即关闭，程序继续运行
# 停止：双击 stop-presence-lock.command
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

if [ ! -f "known_faces.npy" ]; then
    echo "================================================"
    echo "  还没注册你的脸。"
    echo "  先运行一次：./run.sh register.py"
    echo "================================================"
    exit 1
fi

# 防重复启动：已在运行就不重复拉起
# 模式用变量拼接：避免 pkill/pgrep -f 匹配到执行命令的 shell 自身
PAT="main""\.py"
if pgrep -f "$PAT" > /dev/null; then
    echo "presence-lock 已在运行"
    echo "停止请双击 stop-presence-lock.command"
    sleep 2
    exit 0
fi

echo "正在后台启动..."
nohup ./run.sh main.py > presence-lock.log 2>&1 &
echo ""
echo "================================================"
echo "  ✅ 已启动，程序在后台运行"
echo ""
echo "  此窗口现在可以关闭，不影响程序"
echo "  日志：presence-lock.log"
echo "  停止：双击 stop-presence-lock.command"
echo "================================================"
echo ""
read -p "按回车键关闭此窗口（程序继续在后台运行）"
