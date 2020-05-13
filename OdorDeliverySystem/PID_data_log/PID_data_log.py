import time
import serial
from datetime import datetime
import PyCmdMessenger

arduino2 = PyCmdMessenger.ArduinoBoard("com5", baud_rate=115200)
# arduino2 = PyCmdMessenger.ArduinoBoard("/dev/cu.usbmodem1441", baud_rate=115200)
commands2 = [['start_PID_log', '']]
cmd2 = PyCmdMessenger.CmdMessenger(arduino2, commands2)
print('PID_log pre:' + str(datetime.now()))
cmd2.send('start_PID_log')
while(1):
    input = arduino2.readline()
    if input != b'':
        print(datetime.now(), end='\t')
        print(input.decode().replace('\r\n', ''))
