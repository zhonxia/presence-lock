"""解锁模块：锁屏状态下监听唤醒/按键 → 人脸识别 → 注入密码解锁。

前置条件（README 有详细说明）：
1. 宿主进程有辅助功能权限（事件注入需要）——从 iTerm / Terminal 启动，
   并在 系统设置 > 隐私与安全性 > 辅助功能 里给该 app 勾选授权。
2. 钥匙串已存登录密码（只需一次）：
     security add-generic-password -a presence-lock -s presence-lock-unlock -w '你的密码'
3. 系统已开启"屏幕关闭后要求密码"。

技术要点（实验验证）：
- 锁屏检测用 CGSSessionCopyCurrentDictionary 的 CGSSessionScreenIsLocked（实测有效）
- 唤醒检测用 CGDisplayIsAsleep 翻转（黑屏 → 亮屏）
- 锁屏界面按键检测用 HIDIdleTime 归零（ioreg）
- 注入间隔 0.015s 是安全下限，更快会丢字符
"""

import subprocess
import time

import Quartz

import idle
import vision_face

RETURN_KEY = 36
KEY_SERVICE = "presence-lock-unlock"
KEY_ACCOUNT = "presence-lock"

# ---- 键码表（ANSI，实验验证）----
KEYCODES = {
    "a": 0, "b": 11, "c": 8, "d": 2, "e": 14, "f": 3, "g": 5, "h": 4,
    "i": 34, "j": 38, "k": 40, "l": 37, "m": 46, "n": 45, "o": 31, "p": 35,
    "q": 12, "r": 15, "s": 1, "t": 17, "u": 32, "v": 9, "w": 13, "x": 7,
    "y": 16, "z": 6, "0": 29, "1": 18, "2": 19, "3": 20, "4": 21,
    "5": 23, "6": 22, "7": 26, "8": 28, "9": 25,
    "-": 27, "=": 24, "[": 33, "]": 30, "\\": 42, ";": 41, "'": 39,
    ",": 43, ".": 47, "/": 44, "`": 50,
}
SHIFT_KEYS = {
    "A": 0, "B": 11, "C": 8, "D": 2, "E": 14, "F": 3, "G": 5, "H": 4,
    "I": 34, "J": 38, "K": 40, "L": 37, "M": 46, "N": 45, "O": 31, "P": 35,
    "Q": 12, "R": 15, "S": 1, "T": 17, "U": 32, "V": 9, "W": 13, "X": 7,
    "Y": 16, "Z": 6, "!": 18, "@": 19, "#": 20, "$": 21, "%": 23,
    "^": 22, "&": 26, "*": 28, "(": 25, ")": 29, "_": 27, "+": 24,
    "{": 33, "}": 30, "|": 42, ":": 41, '"': 39, "<": 43, ">": 47, "?": 44, "~": 50,
}
SHIFT_MASK = 0x020000  # kCGEventFlagMaskShift


def post_key(keycode, flags=0, delay=0.015):
    down = Quartz.CGEventCreateKeyboardEvent(None, keycode, True)
    Quartz.CGEventSetFlags(down, flags)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
    time.sleep(delay)
    up = Quartz.CGEventCreateKeyboardEvent(None, keycode, False)
    Quartz.CGEventSetFlags(up, flags)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)
    time.sleep(delay)


def inject_text(text):
    for ch in text:
        if ch in KEYCODES:
            post_key(KEYCODES[ch])
        elif ch in SHIFT_KEYS:
            post_key(SHIFT_KEYS[ch], SHIFT_MASK)
        elif ch == " ":
            post_key(49)
        else:
            print(f"[解锁] 警告: 不支持的密码字符 {ch!r}")


def screen_locked():
    """屏幕是否锁定。CGSSessionScreenIsLocked 实测有效。"""
    try:
        d = Quartz.CGSessionCopyCurrentDictionary()
        if not d:
            return False
        return bool(d.get("CGSSessionScreenIsLocked", False))
    except Exception:
        return False


def display_asleep():
    """主显示器是否处于睡眠（黑屏）。"""
    return bool(Quartz.CGDisplayIsAsleep(Quartz.CGMainDisplayID()))


def get_password():
    out = subprocess.run(
        ["security", "find-generic-password", "-a", KEY_ACCOUNT,
         "-s", KEY_SERVICE, "-w"],
        capture_output=True, text=True, timeout=10,
    )
    if out.returncode != 0:
        print("[解锁] 钥匙串没有密码，先执行：")
        print(f"  security add-generic-password -a {KEY_ACCOUNT} -s {KEY_SERVICE} -w '你的密码'")
        return None
    return out.stdout.strip()


def try_unlock(known, threshold):
    """开摄像头识别，识别到本人 → 注入密码解锁。摄像头用完即关。"""
    import cv2
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[解锁] 摄像头打不开，跳过")
        return False
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)  # 480p 采集，同主程序
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    time.sleep(0.6)  # 预热

    matched = False
    for i in range(10):  # 每 0.5 秒一帧，5 秒窗口
        ok, frame = cap.read()
        if not ok:
            continue
        faces = vision_face.extract_faces(frame)
        for vec, bb in faces:
            if vision_face.is_self(vec, known, threshold):
                matched = True
                break
        if matched:
            break
        time.sleep(0.5)
    cap.release()

    if not matched:
        print("[解锁] 5 秒内没识别到本人，跳过")
        return False

    password = get_password()
    if password is None:
        return False
    print("[解锁] 识别到本人，注入密码...")
    time.sleep(0.3)
    inject_text(password)
    post_key(RETURN_KEY)
    print("[解锁] 已注入密码+回车")
    return True


def watch_for_unlock(known, threshold, timeout=3600):
    """锁屏监听：等黑屏→亮屏翻转 或 锁屏界面按键，识别本人 → 解锁。

    返回 True = 已解锁（屏幕回到桌面），False = 超时/未解锁。
    """
    password_check = get_password()
    if password_check is None:
        return False

    start = time.time()
    prev_asleep = display_asleep()
    prev_idle = idle.idle_seconds()  # 下降沿检测用：idle 从大变小 = 刚有人按键
    last_attempt = 0.0
    while time.time() - start < timeout:
        asleep = display_asleep()

        if asleep:
            prev_asleep = asleep
            time.sleep(0.3)
            continue

        # 屏幕亮着
        if prev_asleep and not asleep:
            # 黑屏 → 亮屏翻转（用户按任意键唤醒）
            prev_asleep = asleep
            if screen_locked():
                print("[解锁] 检测到唤醒，识别")
                last_attempt = time.time()
                try_unlock(known, threshold)
                if not screen_locked():
                    return True
            time.sleep(2)
            continue
        prev_asleep = asleep

        if screen_locked():
            # 亮屏锁屏界面：idle 从大变小 = 刚有人按键要解锁 → 识别
            # （不能用 idle<3 判断：Cmd+Ctrl+Q 锁屏本身也是按键，会误触发）
            cur_idle = idle.idle_seconds()
            if (
                cur_idle < 2.0
                and prev_idle > 5.0
                and time.time() - last_attempt >= 5
            ):
                last_attempt = time.time()
                print("[解锁] 检测到按键，识别")
                try_unlock(known, threshold)
                if not screen_locked():
                    return True
            prev_idle = cur_idle
            time.sleep(1.0)  # idle 轮询 1s：ioreg spawn 减半，下降沿检测粒度够
        else:
            # 亮屏且未锁：已解锁或从未锁定
            return True
    return False
