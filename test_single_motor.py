#!/usr/bin/env python3
"""
这个脚本用于单独控制和测试feetech STS3215伺服电机。
可以用于在不运行整个机器人系统的情况下测试单个电机。

使用示例:
```bash
python lerobot/scripts/test_single_motor.py \
  --port /dev/ttyACM1 \
  --id 1 \
  --model sts3215 \
  --test-type rotation
```

测试类型选项:
- rotation: 进行简单的旋转测试，从当前位置旋转一小段角度然后返回
- position: 设置电机到指定位置
- info: 显示电机的各种信息(位置、速度、电压、温度等)
- rotate-degrees: 以角度为单位旋转电机

注意: 对于STS3215电机，全部旋转一圈需要4096步。
默认的旋转测试值为100步，相当于约8.79度(360度/4096*100)。
"""

import argparse
import contextlib
import sys
import time
from pathlib import Path

# 确保可以导入lerobot模块
sys.path.append(str(Path(__file__).parent))

from lerobot.common.robot_devices.motors.configs import FeetechMotorsBusConfig
from lerobot.common.robot_devices.motors.feetech import FeetechMotorsBus


def test_motor_rotation(motors_bus, motor_name, steps=100, delay=1.0):
    """进行简单的旋转测试，从当前位置旋转指定步数然后返回"""
    try:
        if not motors_bus.is_connected:
            print(f"正在连接到电机 {motor_name}...")
            motors_bus.connect()

        # 读取当前位置
        current_position = motors_bus.read("Present_Position", motor_name)
        print(f"当前位置: {current_position}")

        # 启用扭矩
        motors_bus.write("Torque_Enable", 1, motor_name)

        # 正向旋转
        degrees = steps * 360 / 4096  # 将步数转换为角度
        print(f"正在旋转电机，步数: {steps} (约 {degrees:.2f}度)...")
        target_position = current_position + steps
        motors_bus.write("Goal_Position", target_position, motor_name)
        time.sleep(delay)

        # 读取新位置
        new_position = motors_bus.read("Present_Position", motor_name)
        print(f"旋转后位置: {new_position}")

        # 返回原位置
        print("正在返回原位置...")
        motors_bus.write("Goal_Position", current_position, motor_name)
        time.sleep(delay)

        # 读取返回后的位置
        final_position = motors_bus.read("Present_Position", motor_name)
        print(f"返回后位置: {final_position}")

        # 如果只测试一个电机，则在测试结束后断开连接
        if len(motors_bus.motors) == 1:
            motors_bus.write("Torque_Enable", 0, motor_name)
            motors_bus.disconnect()
            print("已断开连接")

    except Exception as e:
        print(f"测试电机 {motor_name} 时出错: {e}")
        if len(motors_bus.motors) == 1:
            with contextlib.suppress(Exception):
                motors_bus.write("Torque_Enable", 0, motor_name)
                motors_bus.disconnect()


def rotate_by_degrees(motors_bus, motor_name, degrees=10.0, delay=1.0):
    """以角度为单位旋转电机"""
    # 将角度转换为步数
    steps = int(degrees * 4096 / 360)
    try:
        if not motors_bus.is_connected:
            print(f"正在连接到电机 {motor_name}...")
            motors_bus.connect()

        # 读取当前位置
        current_position = motors_bus.read("Present_Position", motor_name)
        print(f"当前位置: {current_position}")

        # 启用扭矩
        motors_bus.write("Torque_Enable", 1, motor_name)

        # 正向旋转
        print(f"正在旋转电机 {degrees:.2f}度 (步数: {steps})...")
        target_position = current_position + steps
        motors_bus.write("Goal_Position", target_position, motor_name)
        time.sleep(delay)

        # 读取新位置
        new_position = motors_bus.read("Present_Position", motor_name)
        print(f"旋转后位置: {new_position}")

        # 返回原位置
        print("正在返回原位置...")
        motors_bus.write("Goal_Position", current_position, motor_name)
        time.sleep(delay)

        # 读取返回后的位置
        final_position = motors_bus.read("Present_Position", motor_name)
        print(f"返回后位置: {final_position}")

        # 如果只测试一个电机，则在测试结束后断开连接
        if len(motors_bus.motors) == 1:
            motors_bus.write("Torque_Enable", 0, motor_name)
            motors_bus.disconnect()
            print("已断开连接")

    except Exception as e:
        print(f"测试电机 {motor_name} 时出错: {e}")
        if len(motors_bus.motors) == 1:
            with contextlib.suppress(Exception):
                motors_bus.write("Torque_Enable", 0, motor_name)
                motors_bus.disconnect()


def set_motor_position(motors_bus, motor_name, position):
    """设置电机到指定位置"""
    try:
        if not motors_bus.is_connected:
            print(f"正在连接到电机 {motor_name}...")
            motors_bus.connect()

        # 读取当前位置
        current_position = motors_bus.read("Present_Position", motor_name)
        print(f"当前位置: {current_position}")

        # 启用扭矩
        motors_bus.write("Torque_Enable", 1, motor_name)

        # 设置新位置
        print(f"正在设置电机到位置: {position}...")
        motors_bus.write("Goal_Position", position, motor_name)
        time.sleep(2.0)  # 给电机足够时间移动

        # 读取新位置
        new_position = motors_bus.read("Present_Position", motor_name)
        print(f"设置后位置: {new_position}")

        # 如果只测试一个电机，则在测试结束后断开连接
        if len(motors_bus.motors) == 1:
            motors_bus.write("Torque_Enable", 0, motor_name)
            motors_bus.disconnect()
            print("已断开连接")

    except Exception as e:
        print(f"测试电机 {motor_name} 时出错: {e}")
        if len(motors_bus.motors) == 1:
            with contextlib.suppress(Exception):
                motors_bus.write("Torque_Enable", 0, motor_name)
                motors_bus.disconnect()


def show_motor_info(motors_bus, motor_name):
    """显示电机的详细信息"""
    try:
        if not motors_bus.is_connected:
            print(f"正在连接到电机 {motor_name}...")
            motors_bus.connect()

        # 读取各种电机参数
        position = motors_bus.read("Present_Position", motor_name)
        speed = motors_bus.read("Present_Speed", motor_name)
        load = motors_bus.read("Present_Load", motor_name)
        voltage = motors_bus.read("Present_Voltage", motor_name)
        temperature = motors_bus.read("Present_Temperature", motor_name)

        # 打印信息
        print(f"\n电机 {motor_name} 信息:")
        print(f"  当前位置: {position}")
        print(f"  当前速度: {speed}")
        print(f"  当前负载: {load}")
        print(f"  当前电压: {voltage}")
        print(f"  当前温度: {temperature}°C")

        # 读取其他设置参数
        print("\n电机设置:")
        try:
            motor_id = motors_bus.read("ID", motor_name)
            print(f"  ID: {motor_id}")
            baud_rate = motors_bus.read("Baud_Rate", motor_name)
            print(f"  波特率索引: {baud_rate}")
            torque_enabled = motors_bus.read("Torque_Enable", motor_name)
            print(f"  扭矩启用: {'是' if torque_enabled else '否'}")

            # 尝试读取限制值
            min_limit = motors_bus.read("Min_Angle_Limit", motor_name)
            max_limit = motors_bus.read("Max_Angle_Limit", motor_name)
            print(f"  角度限制: [{min_limit}, {max_limit}]")
        except Exception as e:
            print(f"  读取额外参数时出错: {e}")

    except Exception as e:
        print(f"读取电机 {motor_name} 信息时出错: {e}")


def main():
    parser = argparse.ArgumentParser(description="单独测试和控制feetech伺服电机")
    parser.add_argument("--port", type=str, default="/dev/ttyACM1", help="电机总线端口")
    parser.add_argument("--id", type=int, default=1, help="起始电机ID")
    parser.add_argument(
        "--id_end", type=int, default=None, help="结束电机ID（可选，用于测试一个范围内的所有电机）"
    )
    parser.add_argument("--model", type=str, default="sts3215", help="电机型号 (例如 sts3215)")
    parser.add_argument(
        "--test-type",
        type=str,
        default="rotation",
        choices=["rotation", "position", "info", "rotate-degrees"],
        help="测试类型: rotation (步数旋转测试), rotate-degrees (角度旋转测试), position (设置位置), info (显示信息)",
    )
    parser.add_argument("--steps", type=int, default=100, help="旋转测试的步数 (对于rotation测试类型)")
    parser.add_argument("--degrees", type=float, default=10.0, help="旋转角度 (对于rotate-degrees测试类型)")
    parser.add_argument("--position", type=int, default=2048, help="要设置的位置 (仅用于position测试类型)")
    parser.add_argument("--delay", type=float, default=1.0, help="动作之间的延迟时间(秒)")

    args = parser.parse_args()

    # 确定要测试的电机ID范围
    motor_ids = range(args.id, args.id_end + 1) if args.id_end is not None else [args.id]

    # 创建电机配置字典
    motors_config = {}
    for motor_id in motor_ids:
        motor_name = f"motor_{motor_id}"
        motors_config[motor_name] = (motor_id, args.model)

    # 设置电机配置
    config = FeetechMotorsBusConfig(
        port=args.port,
        motors=motors_config,
    )

    # 创建电机总线对象
    motors_bus = FeetechMotorsBus(config=config)

    # 根据测试类型执行不同的操作
    try:
        for motor_id in motor_ids:
            motor_name = f"motor_{motor_id}"
            print(f"\n===== 测试电机 ID {motor_id} =====")

            if args.test_type == "rotation":
                test_motor_rotation(motors_bus, motor_name, args.steps, args.delay)
            elif args.test_type == "rotate-degrees":
                rotate_by_degrees(motors_bus, motor_name, args.degrees, args.delay)
            elif args.test_type == "position":
                set_motor_position(motors_bus, motor_name, args.position)
            elif args.test_type == "info":
                show_motor_info(motors_bus, motor_name)

            print(f"===== 电机 ID {motor_id} 测试完成 =====\n")

    except Exception as e:
        print(f"测试过程中出错: {e}")


if __name__ == "__main__":
    main()
