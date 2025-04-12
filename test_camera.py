import datetime
import os
import shutil
import subprocess
import threading
import time

import cv2
import numpy as np

# 创建output文件夹（如果不存在）
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)
print(f"图像将保存到: {os.path.abspath(output_dir)}")

# 设置超时环境变量
os.environ["OPENCV_VIDEOIO_DEBUG"] = "1"
os.environ["OPENCV_VIDEOIO_PRIORITY_V4L2"] = "1"
os.environ["V4L2_TIMEOUT_MS"] = "10000"  # 增加超时时间

# 要测试的分辨率列表
resolutions = [
    (640, 480),  # 标准VGA
    (1280, 720),  # 720p
    (1920, 1080),  # 1080p
]


# 读取帧的安全函数（带超时）
def read_frame_with_timeout(cap, timeout=5.0):
    result = [False, None]

    def read_frame():
        nonlocal result
        result = cap.read()

    thread = threading.Thread(target=read_frame)
    thread.daemon = True
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        print(f"读取帧超时 (>{timeout}秒)")
        return False, None

    return result


# 获取当前时间戳作为文件名
def get_timestamp():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


# 检查摄像头支持的格式
def check_camera_formats(camera_id):
    device = f"/dev/video{camera_id}"
    formats = []
    try:
        v4l2_bin = shutil.which("v4l2-ctl")
        if not v4l2_bin:
            print("未找到v4l2-ctl命令，无法检查摄像头格式")
            return ["YUYV"]  # 默认返回YUYV

        result = subprocess.run(
            [v4l2_bin, "--device", device, "--list-formats"], capture_output=True, text=True
        )
        if result.returncode == 0:
            if "MJPG" in result.stdout:
                formats.append("MJPG")
            if "YUYV" in result.stdout:
                formats.append("YUYV")
        return formats
    except Exception as e:
        print(f"检查摄像头格式失败: {e}")
        return ["YUYV"]  # 默认返回YUYV


# 仅测试已知工作的摄像头
for camera_id in [0, 4]:
    print(f"\n===== 测试摄像头 {camera_id} =====")

    # 检查摄像头支持的格式
    formats = check_camera_formats(camera_id)
    print(f"摄像头 {camera_id} 支持的格式: {formats}")

    # 优先使用MJPG格式
    use_mjpg = "MJPG" in formats

    # 测试不同分辨率
    for width, height in resolutions:
        print(f"\n测试分辨率: {width}x{height}")

        # 对于高分辨率，强制使用MJPG（如果支持）
        force_mjpg = use_mjpg and (width > 640 or height > 480)
        format_str = "MJPG" if force_mjpg else "默认"
        print(f"使用格式: {format_str}")

        try:
            # 释放之前的摄像头实例（如果有）
            cap_var = locals().get("cap")
            if cap_var is not None and cap_var.isOpened():
                cap_var.release()
                time.sleep(0.5)

            # 尝试打开摄像头
            print(f"尝试打开摄像头 {camera_id}...")
            cap = cv2.VideoCapture(camera_id, cv2.CAP_V4L2)

            if not cap.isOpened():
                print(f"无法打开摄像头 {camera_id}")
                continue

            # 设置格式（如果需要MJPG）
            if force_mjpg:
                # 设置MJPG格式
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

            # 设置分辨率
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

            # 设置帧率
            cap.set(cv2.CAP_PROP_FPS, 15)

            # 设置缓冲区大小为1，减少延迟
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            # 获取实际设置的参数
            actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = int(cap.get(cv2.CAP_PROP_FPS))
            fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
            fourcc_chars = (
                chr(fourcc_int & 0xFF)
                + chr((fourcc_int >> 8) & 0xFF)
                + chr((fourcc_int >> 16) & 0xFF)
                + chr((fourcc_int >> 24) & 0xFF)
            )

            print(f"请求的分辨率: {width}x{height}")
            print(f"实际的分辨率: {actual_width}x{actual_height}@{actual_fps}fps")
            print(f"使用的格式: {fourcc_chars}")

            # 预热摄像头
            print("预热摄像头...")
            for _ in range(3):
                cap.read()
                time.sleep(0.1)

            # 尝试读取帧和保存图像
            success_count = 0
            for i in range(3):  # 减少测试帧数
                print(f"读取第 {i + 1} 帧...")
                ret, frame = read_frame_with_timeout(cap)

                if ret:
                    success_count += 1
                    # 保存图像
                    filename = f"{output_dir}/camera{camera_id}_{actual_width}x{actual_height}_{fourcc_chars}_{get_timestamp()}.jpg"
                    cv2.imwrite(filename, frame)
                    print(f"成功读取第 {i + 1} 帧，大小: {frame.shape}，已保存到: {filename}")

                    # 如果是第1帧，保存带时间戳的图像
                    if i == 0:
                        # 在图像上添加时间戳和分辨率信息
                        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        info_text = f"Camera {camera_id} | {actual_width}x{actual_height} | {fourcc_chars} | {timestamp}"

                        # 在图像底部添加黑色背景条
                        h, w = frame.shape[:2]
                        info_bg = np.zeros((60, w, 3), dtype=np.uint8)

                        # 将背景条附加到图像底部
                        frame_with_info = np.vstack([frame, info_bg])

                        # 添加文本
                        cv2.putText(
                            frame_with_info,
                            info_text,
                            (10, h + 40),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1,
                            (255, 255, 255),
                            2,
                        )

                        # 保存带信息的图像
                        info_filename = f"{output_dir}/camera{camera_id}_{actual_width}x{actual_height}_{fourcc_chars}_info.jpg"
                        cv2.imwrite(info_filename, frame_with_info)
                        print(f"已保存带信息的图像到: {info_filename}")
                else:
                    print(f"无法读取第 {i + 1} 帧")

                time.sleep(0.2)  # 减少等待时间

            print(f"分辨率 {actual_width}x{actual_height} 测试完成，成功率: {success_count}/3")

        except Exception as e:
            print(f"测试分辨率 {width}x{height} 时出错: {e}")
        finally:
            if "cap" in locals() and cap is not None and cap.isOpened():
                cap.release()
                time.sleep(0.5)

print("\n===== 摄像头测试完成！=====")
print(f"所有图像已保存到: {os.path.abspath(output_dir)}")
print("\n如要在您的项目中使用高分辨率摄像头，请使用以下代码：")
print("""
# 打开摄像头并设置MJPG格式（适用于高分辨率）
cap = cv2.VideoCapture(camera_id, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)  # 设置所需分辨率
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
cap.set(cv2.CAP_PROP_FPS, 15)  # 设置帧率
""")
