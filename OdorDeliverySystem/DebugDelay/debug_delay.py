import PyCmdMessenger
import tkinter as tk
from datetime import datetime
import time
import numpy as np
from numpy.random import permutation
from sklearn import linear_model
import threading
import nidaqmx

com_valve = 'com4'  # Mega2560 board to control valves
arduino_valve = PyCmdMessenger.ArduinoBoard(com_valve, baud_rate=115200)
# arduino = PyCmdMessenger.ArduinoBoard("/dev/cu.usbmodem1441", baud_rate=115200)
commands_valve = [['open_odor_valve', 'ci'],
                  ['switch_panel', '']]
# attach commands to Arduino
cmd = PyCmdMessenger.CmdMessenger(arduino_valve, commands_valve)

def serial_timestamp(arduino):
    """constantly monitor serial, return the timestamp when it's not empty"""
    while(1):
        input = arduino.read()
        if input == b'1':
            print(str(datetime.now()))
            return

valve_symbol = 'A'
valve_duration = 200
for i in range(3):
    print(i)
    print('channel_' + valve_symbol)
    cmd.send('open_odor_valve', valve_symbol, valve_duration)
    print(str(datetime.now()))
    serial_timestamp(arduino_valve)
    serial_timestamp(arduino_valve)
    serial_timestamp(arduino_valve)
    # print('receive:' + str(serial_timestamp(arduino_valve)), end='\t')
    # print('on:' + str(serial_timestamp(arduino_valve)), end='\t')
    # print('off:' + str(serial_timestamp(arduino_valve)))
