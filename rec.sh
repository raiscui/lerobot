#!/bin/bash
conda activate lerobot
# 结束可能占用摄像头的进程
echo "正在释放可能占用摄像头的程序..."
for pid in $(lsof /dev/video* 2>/dev/null | grep -v "COMMAND" | awk '{print $2}' | sort -u); do
    echo "终止进程 $pid ($(ps -p $pid -o comm=))"
    kill -9 $pid 2>/dev/null
done
echo "摄像头资源已释放"

export QT_QPA_PLATFORM=xcb

# 设置串口设备权限
sudo chmod 666 /dev/ttyACM0
sudo chmod 666 /dev/ttyACM1

# 设置摄像头设备权限
echo "设置摄像头设备权限..."
for video_device in /dev/video*; do
    sudo chmod 666 $video_device
    echo "已设置 $video_device 权限"
done

# Delete HuggingFace cache for lerobot/rais
echo "删除 HuggingFace 缓存..."
rm -rf /home/parallels/.cache/huggingface/lerobot/rais/so100_test
rm -rf /Users/cuiluming/.cache/huggingface/lerobot/rais/so100_test
echo "缓存已删除"

# 增加摄像头访问超时值
# export OPENCV_VIDEOIO_DEBUG=1
# export OPENCV_VIDEOIO_PRIORITY_V4L2=1
# export V4L2_TIMEOUT_MS=10000

export LEROBOT_RERUN_MEMORY_LIMIT=80%

python lerobot/scripts/control_robot.py \
  --robot.type=so100 \
  --control.type=record \
  --control.fps=30 \
  --control.single_task="你好" \
  --control.repo_id=rais/so100_test \
  --control.tags='["so100","中文","打招呼"]' \
  --control.warmup_time_s=5 \
  --control.episode_time_s=10 \
  --control.reset_time_s=5 \
  --control.num_episodes=2 \
  --control.push_to_hub=false
