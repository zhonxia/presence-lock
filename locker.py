"""锁屏：pmset displaysleepnow（关闭显示器，唤醒需密码）。

零权限方案。系统设置 > 锁定屏幕 里要开启「屏幕关闭后要求密码」，
否则关屏唤醒不需要密码，等于没锁。安全性等同 Cmd+Ctrl+Q 锁屏。

试过但失败的方案（记录备查）：
- osascript 模拟 Cmd+Ctrl+Q：TCC 检查 osascript 自身，error 1002
- CGEventPost 注入 Cmd+Ctrl+Q：macOS 15 静默丢弃无权限 CLI 的事件
- CGSession -suspend：macOS 15 已移除该工具
"""

import subprocess


def lock_screen():
    r = subprocess.run(["pmset", "displaysleepnow"], capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "pmset 关屏失败")


if __name__ == "__main__":
    import sys
    if "--go" not in sys.argv:
        print("这是锁屏模块。真要测请加 --go 参数（会真的关屏锁住）。")
        sys.exit(0)
    lock_screen()
    print("已锁屏")
