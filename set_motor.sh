sudo chmod 666 /dev/ttyACM0
python lerobot/scripts/configure_motor.py \
  --port /dev/ttyACM1 \
  --brand feetech \
  --model sts3215 \
  --baudrate 1000000 \
  --ID 1
