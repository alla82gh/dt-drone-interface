cmake_minimum_required(VERSION 3.0.2)
project(flight_controller)

find_package(catkin REQUIRED COMPONENTS
  diagnostic_msgs
  duckietown_msgs
  rospy
  sensor_msgs
  std_msgs
)

catkin_package()

catkin_install_python(PROGRAMS
  src/flight_controller_node.py
  src/msp_protocol.py
  src/readonly_msp_probe.py
  src/safety_supervisor.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

install(DIRECTORY config launch
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
)
