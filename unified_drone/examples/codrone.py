from codrone_edu.drone import *                                       # type: ignore

drone = Drone()                                                     # type: ignore
drone.pair()

drone.takeoff()
drone.hover(3)
drone.land()

drone.close()