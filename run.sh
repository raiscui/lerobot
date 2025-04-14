#!/bin/bash

# 结束可能占用摄像头的进程
echo "正在释放可能占用摄像头的程序..."
for pid in $(lsof /dev/video* 2>/dev/null | grep -v "COMMAND" | awk '{print $2}' | sort -u); do
    echo "终止进程 $pid ($(ps -p $pid -o comm=))"
    kill -9 $pid 2>/dev/null
done
echo "摄像头资源已释放"

export LEROBOT_RERUN_MEMORY_LIMIT=1%
# export QT_QPA_PLATFORM=xcb
sudo chmod 666 /dev/ttyACM0
sudo chmod 666 /dev/ttyACM1
uv run lerobot/scripts/control_robot.py \
  --robot.type=so100 \
  --control.type=teleoperate \
  --control.display_data=true
