#!/bin/bash
# presence-lock 停止：双击本文件停止后台运行的 presence-lock
if pkill -f "\.venv/bin/python main\.py" 2>/dev/null; then
    echo "✅ 已停止 presence-lock"
else
    echo "ℹ️ presence-lock 未在运行"
fi
