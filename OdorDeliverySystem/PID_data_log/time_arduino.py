import time
import serial
from datetime import datetime
import PyCmdMessenger

# arduino2 = PyCmdMessenger.ArduinoBoard("com5", baud_rate=115200)
arduino2 = PyCmdMessenger.ArduinoBoard("/dev/cu.usbmodem1441", baud_rate=115200)
commands2 = [['start_time_it', '']]
cmd2 = PyCmdMessenger.CmdMessenger(arduino2, commands2)
cmd2.send('start_time_it')
print('start:' + str(datetime.now()))
# print out the time when Arduino received the command
while(1):
    input = arduino2.readline()
    if input != b'':
        break
print('stop:' + str(datetime.now()))
print(input.decode().replace('\r\n', ''))
