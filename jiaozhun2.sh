conda activate lerobot
export QT_QPA_PLATFORM=xcb

sudo chmod 666 /dev/ttyACM0
sudo chmod 666 /dev/ttyACM1
python lerobot/scripts/control_robot.py \
  --robot.type=so100 \
  --robot.cameras='{}' \
  --control.type=calibrate \
  --control.arms='["main_leader"]'
