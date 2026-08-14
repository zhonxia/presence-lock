#!/usr/bin/env python3
"""注册本人人脸。

运行后正对摄像头：
  s 拍一张（建议拍 3 张：正面、稍侧、稍抬头）
  q 结束并保存

首次运行会触发 macOS 摄像头权限弹窗，请点允许。
"""

import itertools
import json
import os
import sys

import cv2
import numpy as np

import vision_face


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    cfg = json.load(open(os.path.join(base, "config.json"), encoding="utf-8"))

    cap = cv2.VideoCapture(cfg["camera_index"])
    if not cap.isOpened():
        print("无法打开摄像头。首次运行请在弹窗中点允许，然后重试。")
        sys.exit(1)

    print("摄像头已打开。请正对屏幕，光线充足。")
    print("按 s 拍一张（建议 3 张：正面 / 稍侧 / 稍抬头），按 q 结束保存")

    embs = []
    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        faces = vision_face.extract_faces(frame)
        for vec, bb in faces:
            x, y, w, h = bb
            H, W = frame.shape[:2]
            x1, y1 = int(x * W), int((1 - y - h) * H)
            x2, y2 = int((x + w) * W), int((1 - y) * H)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            frame,
            f"faces: {len(faces)}  captured: {len(embs)}  [s]拍 [q]结束",
            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2,
        )
        cv2.imshow("register", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("s"):
            if faces:
                vec, bb = max(faces, key=lambda f: f[1][2] * f[1][3])
                embs.append(vec)
                print(f"已拍摄 {len(embs)} 张")
            else:
                print("画面里没检测到人脸，没拍")
        elif key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

    if not embs:
        print("没拍到任何脸，未保存。")
        sys.exit(1)

    arr = np.array(embs, dtype="<f4")
    out = os.path.join(base, cfg["known_faces_path"])
    np.save(out, arr)
    print(f"已保存 {len(embs)} 张人脸特征到 {out}")

    if len(embs) >= 2:
        ds = [float(np.linalg.norm(a - b)) for a, b in itertools.combinations(embs, 2)]
        print(f"本人照片两两距离: 最小 {min(ds):.3f} / 最大 {max(ds):.3f} / 中位 {np.median(ds):.3f}")
        print(f"经验参考：同人距离通常 <0.5，不同人通常 >0.9。当前阈值 = {cfg['match_threshold']}")
        print("如果经常把别人认成你，调低 config.json 的 match_threshold；如果经常把你认成别人，调高。")
    else:
        print("只拍了 1 张，识别会不够稳。建议再跑一次多拍几张。")


if __name__ == "__main__":
    main()
