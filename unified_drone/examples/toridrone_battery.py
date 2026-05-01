from time import sleep
from CodingRider import *                 #type: ignore
from CodingRider.protocol import *        #type: ignore

def eventState(state):
    print(state.battery)

drone = Drone()                           #type: ignore
drone.open('COM3')
drone.setEventHandler(DataType.State, eventState)
drone.sendRequest(DeviceType.Drone, DataType.state)

sleep(1)