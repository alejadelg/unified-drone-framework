import serial
import time

PORT = "COM3"       # change to your port
BAUDRATE = 9600    # try 115200 if this fails

drone = serial.Serial(PORT, BAUDRATE, timeout=1)

def send_command(cmd):
    drone.write((cmd + "\n").encode())
    time.sleep(0.2)

send_command("mapping_start")
time.sleep(1)
send_command("connect")
time.sleep(1)
send_command("gyroreset")
time.sleep(1)
send_command("start")
time.sleep(1)

send_command("battery?")

response = drone.readline().decode().strip()
print("Battery:", response)

drone.close()