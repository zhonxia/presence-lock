import AVFoundation
import Foundation

// 请求摄像头权限：弹系统窗口等用户决定，输出 granted / denied
var granted = false
let sem = DispatchSemaphore(value: 0)
AVCaptureDevice.requestAccess(for: .video) { ok in
    granted = ok
    sem.signal()
}
sem.wait()
print(granted ? "granted" : "denied")
exit(granted ? 0 : 1)
