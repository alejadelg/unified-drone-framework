from time import sleep
from CodingRider import *                 #type: ignore
from CodingRider.protocol import *        #type: ignore

drone = Drone()                           #type: ignore
drone.open('COM3')

sleep (2)
drone.sendTakeOff()
sleep(3)
drone.sendLanding()