sudo chmod +x lerobot/scripts/test_single_motor.py
sudo chmod 666 /dev/ttyACM1
python lerobot/scripts/test_single_motor.py --port /dev/ttyACM1 --id 1 --test-type info
python lerobot/scripts/test_single_motor.py --port /dev/ttyACM1 --id 1 --test-type position --position 1024
# python lerobot/scripts/test_single_motor.py --port /dev/ttyACM1 --id 1 --model sts3215 --test-type rotation
