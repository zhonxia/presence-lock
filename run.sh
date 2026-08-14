#!/bin/bash
# presence-lock 启动器。
# 清掉外部 PYTHONPATH：Hermes 等宿主环境会注入自己的 Python 路径，
# 不清会导致 import 串到别的 Python 环境（numpy 版本不匹配直接崩）。
cd "$(dirname "$0")"
exec env -u PYTHONPATH .venv/bin/python "$@"
