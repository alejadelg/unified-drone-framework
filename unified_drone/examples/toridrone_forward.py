from time import sleep
from CodingRider.drone import *
from CodingRider.protocol import *

drone = Drone()
drone.open('COM3') 

sleep(2)
drone.sendTakeOff()
sleep(5)
drone.sendControl(0, 50, 0, 0)
sleep(3)
drone.sendLanding()