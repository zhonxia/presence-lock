#!/bin/bash
# presence-lock 停止：双击本文件停止后台运行的 presence-lock
# 模式用变量拼接：避免 pkill -f 匹配到执行命令的 shell 自身（经典坑）
# trap EXIT：任何退出路径都等用户按回车，防止 Terminal 报"会话很快结束"
trap 'echo ""; read -p "按回车键关闭此窗口"' EXIT

PAT="main""\.py"
if pkill -f "$PAT" 2>/dev/null; then
    echo "✅ 已停止 presence-lock"
else
    echo "ℹ️ presence-lock 未在运行"
fi
