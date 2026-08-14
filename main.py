#!/usr/bin/env python3
"""presence-lock：摄像头确认本人在电脑前，不在就锁屏。

状态机：
  ARMED   待机，摄像头关。键鼠空闲超阈值 或 距上次确认超周期 → CHECKING
  CHECKING 摄像头开，每帧判断：本人脸 → 回 ARMED；无人/非本人 → 计时 → ALERT
  ALERT   锁屏前倒计时，期间出现本人脸则取消
  LOCKED  已锁屏，等 60 秒后回 ARMED

用法：
  python main.py           正式运行
  python main.py --dry-run 只检测不锁屏（先试这个）
  python main.py --preview 显示摄像头画面窗口（调试用）
"""

import argparse
import json
import os
import subprocess
import time

import cv2
import numpy as np

import idle
import locker
import vision_face


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_known(path):
    if not os.path.exists(path):
        print(f"没找到注册人脸 {path}，先运行: python register.py")
        raise SystemExit(1)
    return np.load(path)


class Presencer:
    def __init__(self, cfg, known, dry_run=False, preview=False):
        self.cfg = cfg
        self.known = known
        self.dry_run = dry_run
        self.preview = preview
        self.cap = None
        self.state = "ARMED"
        self.last_confirmed = 0.0
        self.absent_since = None
        self.alert_until = 0.0
        self.lock_until = 0.0

    # ---- 摄像头 ----
    def open_cam(self):
        if self.cap is None:
            self.cap = cv2.VideoCapture(self.cfg["camera_index"])
            if not self.cap.isOpened():
                self.cap = None
                return False
            time.sleep(0.8)  # 摄像头预热，避免第一帧黑屏误报
            for _ in range(3):
                self.cap.read()  # 丢弃预热帧
        return True

    def close_cam(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        if self.preview:
            cv2.destroyAllWindows()
            cv2.waitKey(1)  # 让 GUI 事件循环处理窗口销毁（macOS 上必须）

    def read_frame(self):
        ok, frame = self.cap.read()
        return frame if ok else None

    def analyze(self, frame):
        """返回 'self' / 'other' / 'nobody'（取画面中最大的人脸判断）。"""
        faces = vision_face.extract_faces(frame)
        if not faces:
            return "nobody"
        largest = max(faces, key=lambda f: f[1][2] * f[1][3])
        vec, bb = largest
        if vision_face.is_self(vec, self.known, self.cfg["match_threshold"]):
            return "self"
        return "other"

    def show_preview(self, frame, result):
        color = (0, 255, 0) if result == "self" else (0, 0, 255)
        cv2.putText(frame, result, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        cv2.imshow("presence-lock", frame)
        cv2.waitKey(1)

    # ---- 动作 ----
    def notify(self, msg):
        try:
            subprocess.run(
                ["osascript", "-e", f'display notification "{msg}" with title "PresenceLock"'],
                capture_output=True, timeout=5,
            )
        except Exception:
            pass
        print(f"[通知] {msg}", flush=True)

    def lock(self):
        if self.dry_run:
            print("[DRY-RUN] 触发锁屏（未执行）", flush=True)
            return
        try:
            locker.lock_screen()
            print("[已锁屏]", flush=True)
        except Exception as e:
            print(f"[锁屏失败] {e}", flush=True)
            self.notify("锁屏失败：请到 系统设置 > 隐私与安全性 > 辅助功能 授权")

    # ---- 主循环 ----
    def run(self):
        cfg = self.cfg
        print(f"PresenceLock 运行中 (dry_run={self.dry_run}, preview={self.preview})")
        print(f"  空闲 {cfg['idle_threshold_sec']}s 后启动确认；连续 {cfg['absent_lock_sec']}s 没确认到本人则锁屏"
              f"（倒计时 {cfg['alert_sec']}s）")
        print(f"  每 {cfg['recheck_interval_sec']}s 强制复查一次，防陌生人使用")
        print("  Ctrl+C 退出")
        self.last_confirmed = time.time()

        while True:
            now = time.time()
            try:
                if self.state == "ARMED":
                    self.close_cam()
                    idle_s = idle.idle_seconds()
                    since_confirm = now - self.last_confirmed
                    idle_long = idle_s > cfg["idle_threshold_sec"] and since_confirm > cfg["idle_grace_sec"]
                    due_recheck = since_confirm > cfg["recheck_interval_sec"]
                    if idle_long or due_recheck:
                        self.state = "CHECKING"
                        self.absent_since = None
                        print(f"[进入确认] idle={idle_s:.0f}s 距上次确认 {since_confirm:.0f}s", flush=True)
                    time.sleep(1.0)

                elif self.state == "CHECKING":
                    if not self.open_cam():
                        print("[摄像头不可用，5s 后重试]", flush=True)
                        time.sleep(5)
                        continue
                    frame = self.read_frame()
                    if frame is None:
                        time.sleep(2)  # 锁屏界面会占用摄像头，等解锁
                        continue
                    r = self.analyze(frame)
                    if self.preview:
                        self.show_preview(frame, r)
                    if r == "self":
                        self.last_confirmed = now
                        self.absent_since = None
                        self.state = "ARMED"
                        print("[确认本人，回待机]", flush=True)
                    else:
                        if self.absent_since is None:
                            self.absent_since = now
                            print(f"[未确认本人: {r}]", flush=True)
                        absent = now - self.absent_since
                        if absent >= cfg["absent_lock_sec"]:
                            self.state = "ALERT"
                            self.alert_until = now + cfg["alert_sec"]
                            print(f"[{r} 持续 {absent:.0f}s，进入倒计时]", flush=True)
                            if cfg["alert_sec"] > 0:
                                self.notify(f"{cfg['alert_sec']} 秒后锁屏，人在的话看摄像头")
                    time.sleep(cfg["frame_interval_sec"])

                elif self.state == "ALERT":
                    frame = self.read_frame()
                    if frame is not None:
                        r = self.analyze(frame)
                        if r == "self":
                            self.last_confirmed = time.time()
                            self.state = "CHECKING"
                            print("[倒计时取消：本人回来了]", flush=True)
                            time.sleep(cfg["frame_interval_sec"])
                            continue
                    if time.time() >= self.alert_until:
                        self.lock()
                        self.state = "LOCKED"
                        self.lock_until = time.time() + 60
                        self.close_cam()
                    else:
                        time.sleep(0.5)

                elif self.state == "LOCKED":
                    if time.time() >= self.lock_until:
                        self.state = "ARMED"
                        self.last_confirmed = time.time()
                        print("[回到待机]", flush=True)
                    else:
                        time.sleep(5)

            except KeyboardInterrupt:
                print("\n退出")
                self.close_cam()
                break
            except Exception as e:
                print(f"[异常] {e}", flush=True)
                time.sleep(2)


def main():
    ap = argparse.ArgumentParser(description="presence-lock")
    ap.add_argument("--dry-run", action="store_true", help="只检测不锁屏")
    ap.add_argument("--preview", action="store_true", help="显示摄像头画面窗口")
    args = ap.parse_args()

    base = os.path.dirname(os.path.abspath(__file__))
    cfg = load_config(os.path.join(base, "config.json"))
    known = load_known(os.path.join(base, cfg["known_faces_path"]))
    Presencer(cfg, known, dry_run=args.dry_run, preview=args.preview).run()


if __name__ == "__main__":
    main()
