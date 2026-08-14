"""读取系统键鼠空闲时间（秒）。macOS 上通过 ioreg 读 IOHIDSystem 的 HIDIdleTime。"""
import re
import subprocess

_idle_re = re.compile(r'"HIDIdleTime"\s*=\s*(\d+)')


def idle_seconds() -> float:
    """距上次键盘/鼠标活动过去了多少秒。读不到时返回 0.0（视为有人操作）。"""
    try:
        out = subprocess.run(
            ["ioreg", "-c", "IOHIDSystem"],
            capture_output=True, text=True, timeout=5,
        ).stdout
        m = _idle_re.search(out)
        return float(m.group(1)) / 1_000_000_000 if m else 0.0
    except Exception:
        return 0.0


if __name__ == "__main__":
    print(f"idle: {idle_seconds():.1f}s")
