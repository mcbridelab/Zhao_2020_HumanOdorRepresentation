#!/usr/bin/env/python

# read and print out the PID outputs, try reducing the delay in serial
# Zhilei Zhao, Princeton University
# Nov 17, 2017

import datetime as dt
from datetime import datetime
import PyCmdMessenger
import sys
import time


# establish the connection
arduino = PyCmdMessenger.ArduinoBoard("com5", baud_rate=115200)
commands = [['start_session', '']]
cmd = PyCmdMessenger.CmdMessenger(arduino, commands)

#clear the Serial buffer
while(arduino.readline() != b''):
    pass

# print out the start time
print('pre:' + str(datetime.now()))
cmd.send('start_session',)
while(1):
    input = arduino.readline()
    print(input)
    if input != b'':
        time_zero = input.decode().replace('\r\n','')
        break
time_origin = datetime.now()
print('post:' + str(time_origin))
time_zero = int(time_zero)
print(time_zero)


def decode_serial(b):
    s = b.decode().replace('\r\n', '')
    fields = s.split('w')
    if len(fields)<2:
        return None
    ms_diff = int(fields[1]) - time_zero
    time_now = time_origin + dt.timedelta(milliseconds=ms_diff)
    return str(time_now) + '\t' + fields[0]

time.sleep(0.1)

# read and printout the data
with open(sys.argv[1],'w') as f:
    while(True):
        input = arduino.readline()
        if input != b'':
            # print(input)
            res = decode_serial(input)
            if res is not None:
                f.write(decode_serial(input) + '\n')
                # print(decode_serial(input) + '\n')
