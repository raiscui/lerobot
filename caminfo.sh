#!/bin/bash
#  for macos
# ffmpeg -f avfoundation -list_devices true -i ""

# 结束可能占用摄像头的进程
echo "正在释放可能占用摄像头的程序..."
for pid in $(lsof /dev/video* 2>/dev/null | grep -v "COMMAND" | awk '{print $2}' | sort -u); do
    echo "终止进程 $pid ($(ps -p $pid -o comm=))"
    kill -9 $pid 2>/dev/null
done
echo "摄像头资源已释放"

# 等待一秒以确保资源完全释放
sleep 1

# 开始查询摄像头信息
echo "开始查询摄像头信息..."
echo "===== 列出所有视频设备 ====="
v4l2-ctl --list-devices

echo -e "\n===== /dev/video0 信息 ====="
v4l2-ctl -d /dev/video0 --list-formats
v4l2-ctl -d /dev/video0 --get-fmt-video
v4l2-ctl -d /dev/video0 --list-formats-ext

echo -e "\n===== /dev/video2 信息 ====="
v4l2-ctl -d /dev/video2 --list-formats
v4l2-ctl -d /dev/video2 --get-fmt-video
v4l2-ctl -d /dev/video2 --list-formats-ext

echo -e "\n===== /dev/video4 信息 ====="
v4l2-ctl -d /dev/video4 --list-formats
v4l2-ctl -d /dev/video4 --get-fmt-video
v4l2-ctl -d /dev/video4 --list-formats-ext

echo -e "\n摄像头信息查询完成"
