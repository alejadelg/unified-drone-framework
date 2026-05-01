import serial
import time

PORT = "COM3"  
BAUDRATE = 9600  # 9600 or 115200

drone = serial.Serial(PORT, BAUDRATE, timeout=1)

def send_command(cmd):
    command = cmd + "\n"  
    drone.write(command.encode())
    print(f"Send: {cmd}")
    time.sleep(0.1)

send_command("mapping_start")
time.sleep(1)

send_command("connect")
time.sleep(1)

send_command("gyroreset")
time.sleep(1)

send_command("start")
time.sleep(2)

send_command("takeoff")
time.sleep(3)

send_command("forward 200 2000")
time.sleep(2)

send_command("land")

drone.close()