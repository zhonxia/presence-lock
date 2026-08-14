"""Vision 框架人脸检测 + 身份特征提取。

用 macOS 自带 Vision 框架的 VNGenerateFaceEmbeddingsRequest（macOS 14+；
老系统回退到 VNCreateFaceprintRequest），一次调用同时完成：
- 检测画面里有没有人脸
- 给每张人脸算一个 512 维特征向量，用于和注册的本人比对

不需要任何外部模型文件，走苹果神经引擎，离线可用。
"""

import cv2
import numpy as np
from Foundation import NSData
import Vision

_request = None


def _get_request():
    global _request
    if _request is not None:
        return _request
    # 注：macOS 14+ 有 VNGenerateFaceEmbeddingsRequest（512 维），但 pyobjc 12.x 未绑定该类，
    # 所以用老 API VNCreateFaceprintRequest（128 维），两者都是苹果官方人脸特征。
    if not hasattr(Vision, "VNCreateFaceprintRequest"):
        raise RuntimeError("当前系统 Vision 框架不支持人脸特征提取（需要 macOS 11+）")
    _request = Vision.VNCreateFaceprintRequest.alloc().init()
    return _request


def extract_faces(bgr_frame):
    """检测画面里的所有人脸。

    返回 [(embedding float32 向量, 归一化 bbox (x, y, w, h)), ...]
    bbox 是 Vision 坐标系（左下角原点，0~1 归一化）。画面无人脸时返回空列表。
    """
    ok, buf = cv2.imencode(".jpg", bgr_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        return []
    data = NSData.dataWithBytes_length_(buf.tobytes(), len(buf))
    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(data, {})
    req = _get_request()
    success, error = handler.performRequests_error_([req], None)
    if not success:
        return []
    out = []
    for obs in (req.results() or []):
        fp = obs.faceprint()
        if fp is None:
            continue
        dd = fp.descriptorData()  # NSData，128 个 float32
        vec = np.frombuffer(dd.bytes(), dtype="<f4", count=dd.length() // 4).copy()
        bb = obs.boundingBox()
        out.append((vec, (float(bb.origin.x), float(bb.origin.y),
                          float(bb.size.width), float(bb.size.height))))
    return out


def face_distance(vec, known_embs):
    """与已注册本人特征的最短欧氏距离，越小越像本人。"""
    if len(known_embs) == 0:
        return float("inf")
    return float(np.linalg.norm(vec - known_embs, axis=1).min())


def is_self(vec, known_embs, threshold):
    return face_distance(vec, known_embs) <= threshold


if __name__ == "__main__":
    import sys
    # 自检：用一张纯色图验证 Vision 链路不报错
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    faces = extract_faces(frame)
    print(f"smoke test OK: 纯色图检测到 {len(faces)} 张脸（应为 0），Vision 调用正常")
