#!/usr/bin/env python3
"""
高分辨率摄像头配置模块
解决摄像头在高分辨率下的问题，通过使用MJPG格式
使用真实摄像头名称进行配置，支持全称和简称
"""

import contextlib
import json
import logging
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

import cv2

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# 设置环境变量
os.environ["OPENCV_VIDEOIO_DEBUG"] = "1"
os.environ["OPENCV_VIDEOIO_PRIORITY_V4L2"] = "1"
os.environ["V4L2_TIMEOUT_MS"] = "10000"  # 10秒超时

# 摄像头配置（默认配置，将根据实际检测结果动态更新）
DEFAULT_CAMERA_CONFIGS = {
    "default": {  # 默认配置
        "low_res": {
            "width": 640,
            "height": 480,
            "fps": 30,
            "format": None,  # 使用默认格式
        },
        "medium_res": {
            "width": 1280,
            "height": 720,
            "fps": 30,
            "format": None,  # 使用默认格式
        },
        "high_res": {
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "format": None,  # 使用默认格式
        },
    },
    "usb": {  # USB摄像头通用配置
        "low_res": {
            "width": 640,
            "height": 480,
            "fps": 30,
            "format": None,  # 使用默认格式(YUYV)
        },
        "medium_res": {
            "width": 1280,
            "height": 720,
            "fps": 30,
            "format": "MJPG",  # 使用MJPG格式
        },
        "high_res": {
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "format": "MJPG",  # 使用MJPG格式
        },
    },
}


# 设备信息缓存
class CameraRegistry:
    """摄像头设备注册表"""

    def __init__(self):
        # 摄像头信息缓存
        self.devices = {}  # 设备路径 -> 摄像头信息
        self.name_to_device = {}  # 摄像头名称 -> 设备路径
        self.configs = DEFAULT_CAMERA_CONFIGS.copy()  # 摄像头配置
        self.cache_file = "camera_registry.json"
        self.load_from_cache()

    def load_from_cache(self):
        """从缓存文件加载摄像头信息"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file) as f:
                    data = json.load(f)
                    self.devices = data.get("devices", {})
                    self.name_to_device = data.get("name_to_device", {})
                    self.configs = {**DEFAULT_CAMERA_CONFIGS, **data.get("configs", {})}
                    logger.info(f"从缓存加载了 {len(self.devices)} 个摄像头信息")
        except Exception as e:
            logger.warning(f"加载摄像头缓存失败: {e}")

    def save_to_cache(self):
        """保存摄像头信息到缓存文件"""
        try:
            with open(self.cache_file, "w") as f:
                json.dump(
                    {"devices": self.devices, "name_to_device": self.name_to_device, "configs": self.configs},
                    f,
                    indent=2,
                )
            logger.info(f"已保存 {len(self.devices)} 个摄像头信息到缓存")
        except Exception as e:
            logger.warning(f"保存摄像头缓存失败: {e}")

    def scan_devices(self):
        """扫描系统中所有摄像头设备"""
        try:
            # 使用v4l2-ctl --list-devices获取设备列表
            v4l2_bin = shutil.which("v4l2-ctl")
            if not v4l2_bin:
                logger.warning("未找到v4l2-ctl命令，使用备用方法扫描设备")
                return self._scan_devices_fallback()

            output = subprocess.check_output([v4l2_bin, "--list-devices"], stderr=subprocess.PIPE).decode(
                "utf-8", errors="ignore"
            )

            # 清空现有数据
            self.devices = {}
            self.name_to_device = {}

            # 解析输出
            device_blocks = output.split("\n\n")
            for block in device_blocks:
                lines = block.strip().split("\n")
                if not lines:
                    continue

                # 第一行是设备名称
                full_name = lines[0].strip()
                if full_name.endswith(":"):
                    full_name = full_name[:-1].strip()

                # 提取简称（冒号之前的部分）
                short_name = full_name.split(":", 1)[0].strip() if ":" in full_name else full_name

                # 提取设备路径
                video_devices = []
                for line in lines[1:]:
                    line = line.strip()
                    if line.startswith("/dev/video"):
                        video_id = int(line.replace("/dev/video", ""))
                        video_devices.append(video_id)

                if not video_devices:
                    continue

                # 使用第一个video设备作为主设备
                primary_device = video_devices[0]
                device_path = f"/dev/video{primary_device}"

                # 获取设备详细信息
                formats = self._get_device_formats(device_path)

                # 存储设备信息
                self.devices[device_path] = {
                    "full_name": full_name,
                    "short_name": short_name,
                    "device_id": primary_device,
                    "all_devices": video_devices,
                    "formats": formats,
                }

                # 创建名称映射（支持全称和简称）
                self.name_to_device[full_name] = device_path
                self.name_to_device[short_name] = device_path

                # 为每个设备创建一个简单名称映射（如 video0, video4 等）
                for vid in video_devices:
                    simple_name = f"video{vid}"
                    self.name_to_device[simple_name] = f"/dev/video{vid}"

                # 为每个设备创建配置（如果不存在）
                if short_name not in self.configs:
                    if "USB" in full_name or "usb" in full_name:
                        self.configs[short_name] = self.configs["usb"].copy()
                    else:
                        self.configs[short_name] = self.configs["default"].copy()

                    # 如果支持MJPG格式，则在高分辨率配置中启用MJPG
                    if "MJPG" in formats:
                        if "medium_res" in self.configs[short_name]:
                            self.configs[short_name]["medium_res"]["format"] = "MJPG"
                        if "high_res" in self.configs[short_name]:
                            self.configs[short_name]["high_res"]["format"] = "MJPG"

            # 保存到缓存
            self.save_to_cache()

            # 打印扫描结果
            logger.info(f"扫描到 {len(self.devices)} 个摄像头设备")
            return self.devices

        except subprocess.CalledProcessError:
            logger.warning("执行v4l2-ctl命令失败，尝试使用备用方法扫描设备")
            return self._scan_devices_fallback()
        except Exception as e:
            logger.error(f"扫描摄像头设备出错: {e}")
            return self._scan_devices_fallback()

    def _scan_devices_fallback(self):
        """备用扫描方法，当v4l2-ctl命令失败时使用"""
        try:
            # 获取所有video设备
            video_devices = []
            for i in range(10):  # 检查video0到video9
                device_path = f"/dev/video{i}"
                if os.path.exists(device_path):
                    video_devices.append((i, device_path))

            # 清空现有数据
            self.devices = {}
            self.name_to_device = {}

            # 处理每个设备
            for device_id, device_path in video_devices:
                # 创建一个通用名称
                generic_name = f"Camera{device_id}"

                # 获取设备详细信息
                formats = self._get_device_formats(device_path)

                # 存储设备信息
                self.devices[device_path] = {
                    "full_name": generic_name,
                    "short_name": generic_name,
                    "device_id": device_id,
                    "all_devices": [device_id],
                    "formats": formats,
                }

                # 创建名称映射
                self.name_to_device[generic_name] = device_path
                self.name_to_device[f"video{device_id}"] = device_path

                # 为每个设备创建配置（如果不存在）
                if generic_name not in self.configs:
                    if "MJPG" in formats:
                        self.configs[generic_name] = self.configs["usb"].copy()
                    else:
                        self.configs[generic_name] = self.configs["default"].copy()

            # 保存到缓存
            self.save_to_cache()

            # 打印扫描结果
            logger.info(f"备用方法扫描到 {len(self.devices)} 个摄像头设备")
            return self.devices

        except Exception as e:
            logger.error(f"备用扫描方法出错: {e}")
            return {}

    def _get_device_formats(self, device_path):
        """获取设备支持的格式"""
        formats = []
        try:
            v4l2_bin = shutil.which("v4l2-ctl")
            if not v4l2_bin:
                logger.debug(f"未找到v4l2-ctl命令，无法获取设备 {device_path} 格式")
                return formats

            output = subprocess.check_output(
                [v4l2_bin, "--device", device_path, "--list-formats"], stderr=subprocess.PIPE
            ).decode("utf-8", errors="ignore")

            if "MJPG" in output or "Motion-JPEG" in output:
                formats.append("MJPG")
            if "YUYV" in output:
                formats.append("YUYV")

            return formats
        except Exception as e:
            logger.debug(f"获取设备 {device_path} 格式时出错: {e}")
            return formats

    def get_camera_id(self, camera_name):
        """根据摄像头名称获取设备ID"""
        # 如果是数字，则直接返回
        if isinstance(camera_name, int) or (isinstance(camera_name, str) and camera_name.isdigit()):
            return int(camera_name)

        # 如果是设备路径，提取ID
        if camera_name.startswith("/dev/video"):
            try:
                return int(camera_name.replace("/dev/video", ""))
            except ValueError:
                pass

        # 检查是否需要重新扫描设备
        if not self.devices:
            self.scan_devices()

        # 查找设备
        device_path = self.name_to_device.get(camera_name)
        if device_path:
            return self.devices[device_path]["device_id"]

        # 尝试模糊匹配
        for name, path in self.name_to_device.items():
            if camera_name.lower() in name.lower():
                return self.devices[path]["device_id"]

        # 未找到匹配项，返回默认值
        logger.warning(f"未找到摄像头 '{camera_name}'，使用默认ID 0")
        return 0

    def get_camera_info(self, camera_name):
        """获取摄像头详细信息"""
        # 检查是否需要重新扫描设备
        if not self.devices:
            self.scan_devices()

        # 如果是数字ID，转换为设备路径
        if isinstance(camera_name, int) or (isinstance(camera_name, str) and camera_name.isdigit()):
            device_path = f"/dev/video{int(camera_name)}"
            if device_path in self.devices:
                return self.devices[device_path]

        # 如果是设备路径，直接查找
        if camera_name.startswith("/dev/video") and camera_name in self.devices:
            return self.devices[camera_name]

        # 按名称查找
        device_path = self.name_to_device.get(camera_name)
        if device_path:
            return self.devices[device_path]

        # 尝试模糊匹配
        for name, path in self.name_to_device.items():
            if camera_name.lower() in name.lower():
                return self.devices[path]

        # 未找到匹配项
        return None

    def get_camera_config(self, camera_name, resolution="medium_res"):
        """获取摄像头配置"""
        # 检查是否需要重新扫描设备
        if not self.devices:
            self.scan_devices()

        # 尝试查找摄像头信息
        camera_info = self.get_camera_info(camera_name)
        if not camera_info:
            logger.warning(f"未找到摄像头 '{camera_name}' 的信息，使用默认配置")
            return DEFAULT_CAMERA_CONFIGS["default"][resolution].copy()

        # 获取简称
        short_name = camera_info["short_name"]

        # 查找配置
        if short_name in self.configs and resolution in self.configs[short_name]:
            return self.configs[short_name][resolution].copy()

        # 使用默认配置
        logger.warning(f"未找到摄像头 '{camera_name}' 的 {resolution} 配置，使用默认配置")

        # 根据是否支持MJPG选择合适的默认配置
        if "MJPG" in camera_info["formats"] and resolution in ["medium_res", "high_res"]:
            return DEFAULT_CAMERA_CONFIGS["usb"][resolution].copy()
        else:
            return DEFAULT_CAMERA_CONFIGS["default"][resolution].copy()

    def list_cameras(self):
        """列出所有可用的摄像头"""
        # 确保设备已扫描
        if not self.devices:
            self.scan_devices()

        # 打印摄像头列表
        print("\n可用摄像头列表:")
        print("=" * 50)

        for device_path, info in self.devices.items():
            full_name = info["full_name"]
            short_name = info["short_name"]
            device_id = info["device_id"]
            formats = ", ".join(info["formats"]) if info["formats"] else "未知"

            print(f"摄像头: {short_name}")
            print(f"  完整名称: {full_name}")
            print(f"  设备路径: {device_path} (ID: {device_id})")
            print(f"  支持的格式: {formats}")
            print("-" * 50)

    def update_camera_config(self, camera_name, resolution, config):
        """更新摄像头配置"""
        # 获取摄像头信息
        camera_info = self.get_camera_info(camera_name)
        if not camera_info:
            logger.warning(f"未找到摄像头 '{camera_name}'，无法更新配置")
            return False

        # 获取简称
        short_name = camera_info["short_name"]

        # 确保配置存在
        if short_name not in self.configs:
            self.configs[short_name] = DEFAULT_CAMERA_CONFIGS["default"].copy()

        # 更新配置
        self.configs[short_name][resolution] = config

        # 保存到缓存
        self.save_to_cache()

        return True


# 创建全局注册表实例
registry = CameraRegistry()


class Camera:
    """高分辨率摄像头类，使用真实摄像头名称进行配置"""

    def __init__(self, camera_name, resolution="medium_res", fps=None):
        """
        初始化摄像头

        参数:
            camera_name (str): 摄像头名称，可以是全称、简称或ID
            resolution (str): 分辨率类型 ('low_res', 'medium_res', 'high_res')
            fps (int): 自定义帧率，如果设置则覆盖默认帧率
        """
        self.camera_name = camera_name
        self.resolution = resolution
        self.cap = None

        # 获取摄像头ID
        self.camera_id = registry.get_camera_id(camera_name)

        # 获取摄像头信息
        info = registry.get_camera_info(camera_name)
        if info:
            self.camera_info = info
            self.camera_name = info["short_name"]
        else:
            self.camera_info = {
                "full_name": f"Camera{self.camera_id}",
                "short_name": f"Camera{self.camera_id}",
                "device_id": self.camera_id,
                "formats": [],
            }

        # 获取配置
        self.config = registry.get_camera_config(camera_name, resolution)

        # 覆盖帧率（如果指定）
        if fps is not None:
            self.config["fps"] = fps

    def open(self):
        """打开摄像头并应用配置"""
        # 释放可能占用的资源
        if self.cap is not None:
            self.release()

        # 打开摄像头
        self.cap = cv2.VideoCapture(self.camera_id, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            logger.error(f"无法打开摄像头 '{self.camera_name}' (ID: {self.camera_id})")
            return False

        # 设置格式（如果指定）
        if self.config["format"] == "MJPG":
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

        # 设置分辨率和帧率
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config["width"])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config["height"])
        self.cap.set(cv2.CAP_PROP_FPS, self.config["fps"])

        # 设置缓冲区大小为1，减少延迟
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # 验证设置
        actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = int(self.cap.get(cv2.CAP_PROP_FPS))

        # 获取实际使用的格式
        fourcc_int = int(self.cap.get(cv2.CAP_PROP_FOURCC))
        format_chars = "".join([chr((fourcc_int >> 8 * i) & 0xFF) for i in range(4)])

        logger.info(f"摄像头 '{self.camera_name}' (ID: {self.camera_id}) 已打开:")
        logger.info(f"  分辨率: {actual_width}x{actual_height}")
        logger.info(f"  帧率: {actual_fps}")
        logger.info(f"  格式: {format_chars}")

        # 预热摄像头
        for _ in range(5):
            self.cap.read()
            time.sleep(0.05)

        return True

    def read(self, timeout=3.0):
        """安全地读取一帧，带有超时处理"""
        if self.cap is None or not self.cap.isOpened():
            logger.error("摄像头未打开")
            return False, None

        result = [False, None]
        exception = None

        def read_frame():
            nonlocal result, exception
            try:
                result = self.cap.read()
            except Exception as e:
                exception = e

        thread = threading.Thread(target=read_frame)
        thread.daemon = True
        thread.start()
        thread.join(timeout)

        if thread.is_alive():
            logger.warning(f"读取帧超时 (>{timeout}秒)")
            return False, None

        if exception:
            logger.error(f"读取帧时发生异常: {exception}")
            return False, None

        return result

    def release(self):
        """释放摄像头资源"""
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
            self.cap = None

    def __del__(self):
        """析构函数，确保释放资源"""
        self.release()

    @staticmethod
    def kill_blocking_processes():
        """终止可能阻塞摄像头的进程"""
        try:
            # 使用Python逻辑替代shell管道
            lsof_bin = shutil.which("lsof")
            if not lsof_bin:
                logger.warning("找不到lsof命令，无法检测占用摄像头的进程")
                return

            # 安全地获取占用摄像头的进程
            video_devices = []
            for i in range(10):
                device = f"/dev/video{i}"
                if os.path.exists(device):
                    video_devices.append(device)

            if not video_devices:
                return

            cmd = [lsof_bin] + video_devices
            output = subprocess.check_output(cmd, stderr=subprocess.PIPE).decode("utf-8").strip()

            # 从输出中解析PID
            if not output:
                return

            pids = set()
            for line in output.split("\n"):
                if line and not line.startswith("COMMAND"):  # 跳过标题行
                    parts = line.split()
                    if len(parts) > 1:
                        try:
                            pids.add(parts[1])  # PID通常在第二列
                        except (IndexError, ValueError):
                            continue

            # 终止进程
            for pid in pids:
                logger.info(f"终止占用摄像头的进程: {pid}")
                kill_bin = shutil.which("kill")
                if kill_bin:
                    subprocess.run([kill_bin, "-9", pid], check=False)
        except Exception as e:
            logger.warning(f"清理摄像头进程时出错: {e}")

    @staticmethod
    def list_cameras():
        """列出所有可用的摄像头"""
        registry.list_cameras()

    @staticmethod
    def scan_cameras():
        """扫描并更新摄像头信息"""
        registry.scan_devices()
        registry.list_cameras()


# 创建caminfo.sh脚本，用于显示摄像头信息
def create_camera_info_script():
    """创建摄像头信息脚本"""
    script_path = Path("caminfo.sh")

    script_content = """#!/bin/bash
# 摄像头信息查询脚本

# 设置终端颜色
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}===== 摄像头设备列表 =====${NC}"
v4l2-ctl --list-devices

echo -e "${YELLOW}\n===== 设备详细信息 =====${NC}"
for device in /dev/video*; do
    if [ -e "$device" ]; then
        echo -e "${GREEN}$device${NC}:"
        v4l2-ctl --device=$device --all | grep -E 'Format Video|Card Type|Driver|Bus info' | sed 's/^/  /'
        echo -e "${YELLOW}  支持的格式:${NC}"
        v4l2-ctl --device=$device --list-formats | grep -v "ioctl" | sed 's/^/    /'
        echo ""
    fi
done

echo -e "${GREEN}===== 已连接的USB设备 =====${NC}"
lsusb | grep -i camera
"""

    with open(script_path, "w") as f:
        f.write(script_content)

    # 设置执行权限，改为更安全的0o700权限
    os.chmod(script_path, 0o700)
    logger.info(f"已创建摄像头信息脚本: {script_path}")


# 创建getcam.sh脚本，用于简化摄像头使用
def create_getcam_script():
    """创建摄像头工具脚本"""
    script_path = Path("getcam.sh")

    script_content = """#!/bin/bash
# 摄像头工具脚本

# 设置终端颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 显示帮助
show_help() {
    echo -e "${GREEN}摄像头工具脚本${NC}"
    echo "用法: $0 [选项] [摄像头ID/名称]"
    echo ""
    echo "选项:"
    echo "  -h, --help       显示帮助信息"
    echo "  -l, --list       列出所有摄像头"
    echo "  -t, --test       测试指定摄像头"
    echo "  -i, --info       显示摄像头详细信息"
    echo "  -r, --res RES    设置分辨率 (low, medium, high)"
    echo ""
    echo "示例:"
    echo "  $0 -l                   # 列出所有摄像头"
    echo "  $0 -t \"USB Camera\"     # 测试USB摄像头"
    echo "  $0 -t 0 -r high         # 以高分辨率测试摄像头0"
}

# 默认参数
ACTION="list"
CAMERA_ID=""
RESOLUTION="medium"

# 解析参数
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -h|--help)
            show_help
            exit 0
            ;;
        -l|--list)
            ACTION="list"
            shift
            ;;
        -t|--test)
            ACTION="test"
            if [[ $2 != -* && $2 != "" ]]; then
                CAMERA_ID="$2"
                shift
            fi
            shift
            ;;
        -i|--info)
            ACTION="info"
            shift
            ;;
        -r|--res)
            if [[ $2 == "low" || $2 == "medium" || $2 == "high" ]]; then
                RESOLUTION="$2"
                shift
            else
                echo -e "${RED}错误: 无效的分辨率参数 '$2' (使用low/medium/high)${NC}"
                exit 1
            fi
            shift
            ;;
        *)
            # 如果没有前缀，则认为是摄像头ID
            if [[ $1 != -* ]]; then
                CAMERA_ID="$1"
            else:
                echo -e "${RED}未知选项: $1${NC}"
                show_help
                exit 1
            fi
            shift
            ;;
    esac
done

# 执行操作
case $ACTION in
    list)
        echo -e "${GREEN}正在扫描摄像头...${NC}"
        python -c "from camera_config_hd import Camera; Camera.list_cameras()"
        ;;
    info)
        echo -e "${GREEN}摄像头详细信息:${NC}"
        ./caminfo.sh
        ;;
    test)
        if [[ -z $CAMERA_ID ]]; then
            echo -e "${RED}错误: 必须指定摄像头ID或名称${NC}"
            show_help
            exit 1
        fi
        echo -e "${GREEN}正在测试摄像头 $CAMERA_ID (分辨率: $RESOLUTION)...${NC}"
        case $RESOLUTION in
            low)
                RES_ARG="low_res"
                ;;
            medium)
                RES_ARG="medium_res"
                ;;
            high)
                RES_ARG="high_res"
                ;;
        esac

        # 使用Python脚本测试摄像头
        python -c "
from camera_config_hd import Camera
import cv2
import time
import datetime

try:
    print(f'测试摄像头: $CAMERA_ID, 分辨率: $RES_ARG')
    cam = Camera('$CAMERA_ID', resolution='$RES_ARG')
    if cam.open():
        # 读取一帧
        ret, frame = cam.read()
        if ret:
            print(f'成功读取帧，大小: {frame.shape}')
            # 生成文件名
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'camera_{cam.camera_name}_{timestamp}.jpg'
            # 保存图像
            cv2.imwrite(filename, frame)
            print(f'已保存图像到: {filename}')
        else:
            print('读取帧失败')

        # 释放资源
        cam.release()
except Exception as e:
    print(f'测试摄像头时出错: {e}')
"
        ;;
esac
"""

    with open(script_path, "w") as f:
        f.write(script_content)

    # 设置执行权限，改为更安全的0o700权限
    os.chmod(script_path, 0o700)
    logger.info(f"已创建摄像头工具脚本: {script_path}")


# 示例用法
if __name__ == "__main__":
    # 创建辅助脚本
    create_camera_info_script()
    create_getcam_script()

    # 终止占用摄像头的进程
    Camera.kill_blocking_processes()

    # 设置视频设备权限
    for i in range(10):
        device = f"/dev/video{i}"
        if os.path.exists(device):
            with contextlib.suppress(Exception):
                # 获取sudo的完整路径
                sudo_bin = shutil.which("sudo")
                chmod_bin = shutil.which("chmod")
                if sudo_bin and chmod_bin:
                    subprocess.run([sudo_bin, chmod_bin, "666", device], check=False)

    # 扫描并列出摄像头
    Camera.scan_cameras()

    # 测试示例
    print("\n测试示例:")
    print("1. 通过名称使用摄像头:")
    print("   cam = Camera(\"USB Camera\", resolution='high_res')")
    print("2. 通过完整名称使用摄像头:")
    print('   cam = Camera("FaceTime高清相机: FaceTime (usb-0000:00:03.0-3)")')
    print("3. 通过ID使用摄像头:")
    print("   cam = Camera(0)")
    print("\n可使用 ./caminfo.sh 查看详细摄像头信息")
    print("可使用 ./getcam.sh 进行摄像头测试\n")
