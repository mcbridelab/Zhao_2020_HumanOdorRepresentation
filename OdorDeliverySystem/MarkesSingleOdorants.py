#!/usr/bin/env/python

# Zhilei Zhao, Princeton University
# zhileiz@princeton.edu
# Nov 09, 2017
# GUI to control the odor delivery system
# comminucate to Arduino board with serial


import PyCmdMessenger
import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext
from tkinter import messagebox
from tkinter import filedialog
from datetime import datetime
import time
import numpy as np
from numpy.random import permutation
from sklearn import linear_model
import threading
import nidaqmx
from multiprocessing import Process


def pattern_parser(pattern):
    """parse the odor pattern string into parameter value lists"""
    # example: pattern 'A3_Z10_J3_#_Z5_N2;1'
    # parsed:[6, 'A', 300, 'Z', 1000, 'J', 300, '#', 0, 'Z', 500, 'N', 200]
    # 1st int is the number of channels including Z and #
    # for repeated pattern, duplicate items in the list
    num_channels = 0
    # repeats number separate by ;
    pattern_fields = pattern.split(';')
    if len(pattern_fields) == 1:
        repeat = 1
    else:
        repeat = int(pattern_fields[1])
    stream = pattern_fields[0]
    parameters_value_temp = []
    num_channels = 0
    fields = stream.split('_')
    for f in fields:
        if 'W' in f:
            info = f.split('W')
            valve = info[0] + 'W'
            duration = int(float(info[1]) * 100)  # time unit is 10ms
        else:
            valve = f[0]
            if valve == '#':
                parameters_value_temp += [valve, 0]
                num_channels += 1
                continue
            duration = int(float(f[1:]) * 100)  # time unit is 10ms
        parameters_value_temp += [valve, duration]
        num_channels += 1
    parameters_value = [repeat, [num_channels] + parameters_value_temp]
    # cases where only odor or CO2 is specified, add an empty list
    return parameters_value
    # print(parameters_value_final)


def when_interrupted():
    """operations when Stop button is pressed"""
    # reset the Start and Stop button
    button_start.configure(text='Start', state='active')
    button_stop.configure(state='disabled')
    # reset the global flag
    global interrupted
    interrupted = 0


def wait_ms(ms):
    """wait ms milliseconds"""
    time_ori = datetime.now()
    while(1):
        time_elapse = datetime.now() - time_ori
        # convert to ms
        time_elapse_ms = time_elapse.seconds * 1000 + time_elapse.microseconds / 1000
        # need to constantly check if interrupted
        if interrupted or time_elapse_ms > ms:
            break


def serial_timestamp(arduino):
    """constantly monitor serial, return the timestamp when it's not empty"""
    while(1):
        input = arduino.read()
        if input == b'1':  # get some input from Arduino
            print(str(datetime.now()))
            return


def daq_ttl_thread(symbol, duration):
    """generate a square TTL for DAQ line for the valve"""
    def daq_ttl_thread_callback():
        # start trigger ttl
        print('triggerStart for ' + symbol + ':', end='')
        start_write_time = datetime.now()
        print(str(start_write_time))
        daq_task.write([True, False])  # write function takes time
        wait_ms(acquisition_on)
        daq_task.write([False, False])
        t = datetime.now() - start_write_time
        start_take_time = t.seconds * 1000 + t.microseconds / 1000
        # wait until stop trigger ttl
        wait_ms(acquisition_pre * 1000 + duration * 10 + acquisition_post * 1000 - start_take_time)
        print('triggerStop for ' + symbol + ':', end='')
        print(str(datetime.now()))
        daq_task.write([False, True])
        print('>>>>>')
        wait_ms(acquisition_on)
        daq_task.write([False, False])
        return
    t2 = threading.Thread(target=daq_ttl_thread_callback)
    t2.start()


def daq_ttl_thread_simple(total_duration):
    """generate a square TTL for DAQ line based on total recording duration"""
    def daq_ttl_thread_simple_callback():
        # start trigger ttl
        print('triggerStart at:', end='')
        start_write_time = datetime.now()
        print(str(start_write_time))
        daq_task.write([True, False])  # write function takes time
        wait_ms(acquisition_on)
        daq_task.write([False, False])
        t = datetime.now() - start_write_time
        start_take_time = t.seconds * 1000 + t.microseconds / 1000
        # wait until stop trigger ttl
        wait_ms(total_duration*1000 - start_take_time)
        print('triggerStop at: ', end='')
        print(str(datetime.now()))
        daq_task.write([False, True])
        print('>>>>>')
        wait_ms(acquisition_on)
        daq_task.write([False, False])
        return
    t5 = threading.Thread(target=daq_ttl_thread_simple_callback)
    t5.start()

# log = open('temp.txt', 'w')
def daq_ttl_thread_markes(open_CO2=False, delay_duration=3, co2_duration=3):
    """monitoring the trap firing time from Markes"""
    def daq_ttl_thread_markes_callback():
        # start trigger ttl
        # while not daq_task2.read():
        #     a=1
        # print(datetime.now())
        # print('Trap fire time, see above')
        # read 4 bytes, if all true, then it's on
        # single byte may suffer from noise
        flag_continue = 1
        a1 = daq_task2.read()
        a2 = daq_task2.read()
        a3 = daq_task2.read()
        while flag_continue:
            a4 = daq_task2.read()
            if a1 and a2 and a3 and a4:
                flag_continue = 0
            a1 = a2
            a2 = a3
            a3 = a4
            # a = daq_task2.read()
            # log.write(str(datetime.now())+'\t'+str(a)+'\n')
        time_fire = datetime.now()
        print('Trap fire at:' + str(time_fire))
        if open_CO2:
            wait_ms(delay_duration*1000)
            cmd.send('open_CO2_valve', co2_duration * 100)
            print('CO2 valve opened at:', str(datetime.now()))
        return
    t3 = threading.Thread(target=daq_ttl_thread_markes_callback)
    t3.start()


def calculate_flush(total_dur):
    """calculate how to divide the total_dur into regular
    z-flush and extra-flush, remaining time is regular z-
    flush to establish a flowrate balance"""
    pre_flush_dur = 300  # unit 10ms
    extra_flush_dur = total_dur - 3 * pre_flush_dur
    return pre_flush_dur, extra_flush_dur


def go_through_pattern(arduino, cmd, parameters_value):
    """go through the odor delivery pattern in a separate thread"""
    print(parameters_value)
    num_repeat = parameters_value[0]
    odor_pattern = parameters_value[1]
    num_valves = odor_pattern[0]
    print('num_repeat', num_repeat)
    def go_through_pattern_callback():
        for r in range(num_repeat):
            for n_v in range(num_valves):
                if interrupted:
                    break
                idx = 1 + n_v * 2  # the idx of valve in the pattern list
                valve_symbol = odor_pattern[idx]
                valve_duration = odor_pattern[idx + 1]   # in unit of 10ms)
                if valve_symbol == 'Z':
                    # added 20180827: extra flush Control
                    [pre_flush_dur, extra_flush_dur] = calculate_flush(valve_duration)
                    # [pre_flush_dur, extra_flush_dur] = [300, 2000]  # unit of 10ms
                    cmd.send('extra_flush', pre_flush_dur, extra_flush_dur)
                    # this a control valve, if next channel is an odor channel
                    # need to send DAQ START signal for it
                    if n_v < odor_pattern[0] - 1 and \
                            odor_pattern[idx + 2][0] in all_valves+['W']:
                        # wait ms before start image acquisition
                        wait_ms(valve_duration * 10 - acquisition_pre * 1000)
                        # send the start signal and print timestamp
                        # daq_ttl(start_line)
                        # print('triggerStart for ' + parameters_value[idx+2] + \
                        # ": " + str(datetime.now()))
                        # start a new thread in order to send DAQ STOP signal
                        # 20180918 comment this line to disable trigger
                        daq_ttl_thread(odor_pattern[idx+2], odor_pattern[idx+3])
                        # wait a little more until send signal to Arduino
                        # print(acquisition_pre * 1000 - acquisition_on - prepare)
                        # print(str(datetime.now()))
                        wait_ms(acquisition_pre * 1000 - acquisition_on - prepare)
                        # print(str(datetime.now()))
                    else:
                        # Z is the last channel or next channel is not odor channel
                        # do nothing but wait
                        wait_ms(valve_duration * 10 - prepare)   # in unit of ms
                elif valve_symbol == '#':
                    total_switch_dur = 3000  # in unit of 10ms
                    [pre_flush_dur, extra_flush_dur] = calculate_flush(total_switch_dur)
                    # [pre_flush_dur, extra_flush_dur] = [300, 2000]  # unit of 10ms
                    cmd.send('extra_flush', pre_flush_dur, extra_flush_dur)
                    print('flushing manifold before switching')
                    wait_ms(total_switch_dur * 10 + 3000)  # wait 33s to flush the old manifold
                    cmd.send('switch_panel')
                    print('switchPanel:' + str(datetime.now()))
                    cmd.send('extra_flush', pre_flush_dur, extra_flush_dur)
                    print('flushing manifold after switching')
                    wait_ms(total_switch_dur * 10 + 3000)  # wait 33s to flush the new manifold
                elif valve_symbol == 'W' or valve_symbol == 'w':
                    # lower case 'w' means don't start DAQ trigger
                    # CO2 valve only
                    cmd.send('open_CO2_valve', valve_duration)
                    print('CO2\n'+str(datetime.now()))
                    serial_timestamp(arduino_valve)
                    serial_timestamp(arduino_valve)
                    serial_timestamp(arduino_valve)
                else:
                    # odor valve, send command to Arduino
                    # monitor serial and print out timestamp
                    print('channel_' + valve_symbol)
                    if len(valve_symbol)==1:
                        cmd.send('open_odor_valve', valve_symbol, valve_duration)
                    else:
                        cmd.send('open_odor_CO2', valve_symbol[0], valve_duration)
                    print(str(datetime.now()))
                    serial_timestamp(arduino_valve)
                    serial_timestamp(arduino_valve)
                    serial_timestamp(arduino_valve)
            # loop is finished, reset the Start and Stop button and flag
        when_interrupted()
        return
    # use a new thread, to avoid freezing the GUI
    t1 = threading.Thread(target=go_through_pattern_callback)
    t1.start()


def start_loop(markes_bool=False):
    """start the delivery pattern loop"""
    # parse the odor pattern to get parameter types and values
    if markes_bool:
        idx = markes_single_odorant_entry.get()
    else:
        idx = block_idx_entry.get()
    idx = int(idx) - 1
    pattern_string_entry = pattern_string_entries[idx]
    pattern = pattern_string_entry.get()
    parameters_value = pattern_parser(pattern)
    if parameters_value is None:
        return None
    # change the states for start and stop button
    button_start.configure(text='Running', state='disabled')
    button_stop.configure(state='active')
    # print out valve information
    get_valve_info()
    print('pattern:' + str(parameters_value))
    print('>>>>>')
    # loop through the pattern, open the valve one by one
    go_through_pattern(arduino_valve, cmd, parameters_value)


def stop_loop():
    """stop button is pressed"""
    global interrupted
    interrupted = 1
    print('interrupted:' + str(datetime.now()), end='\t')


def enable_random():
    """when user choose random generated pattern"""
    pattern_string_entry.delete('1.0', 'end-1c')
    button_generate.configure(state='active')


def disable_random():
    """when user choose user-specified pattern"""
    button_generate.configure(state='disabled')


def random_generate():
    """generate the pattern string randomly"""
    # delete the existing string first
    pattern_string_entry.delete("1.0", tk.END)
    res = []
    # get the constraints
    on_dur = random_on_dur_entry.get()
    off_dur = random_off_dur_entry.get()
    random_channels = random_channels_entry.get()
    num_puffs = num_puffs_entry.get()
    # separate channels into two lists based on what panel they belong
    rc_1 = []
    rc_2 = []
    for v in random_channels:
        if v > 'K':
            rc_2.append(v)
        else:
            rc_1.append(v)
    # permute the channel string
    if rc_1 and rc_2:
        num_panels = 2
    else:
        num_panels = 1
    for i in range(int(num_puffs)):
        if i > 0 and num_panels > 1:
            res.append('#')
        channel_permute_1 = permutation(list(rc_1))
        channel_permute_2 = permutation(list(rc_2))
        for v in channel_permute_1:
            res.append('Z' + off_dur + '_' + v + on_dur)
        if num_panels > 1:
            res.append('#')  # the symbol respresents switch panel
        for v in channel_permute_2:
            res.append('Z' + off_dur + '_' + v + on_dur)
    res.append('Z' + off_dur)
    pattern_string_entry.insert(tk.INSERT, '_'.join(res))


def flow_setup():
    """send command to arduino to setup the flowrate"""
    flow_rate_carrier = int(flow_carrier_entry.get())
    # flow_rate_ctrl = int(flow_ctrl_entry.get())
    flow_rate_odor = int(flow_odor_entry.get())
    flow_rate_ctrl = flow_rate_odor
    flow_rate_CO2 = int(flow_CO2_entry.get())
    flow_rate_ctrl2 = flow_rate_CO2
    flow_voltage_carrier = MFC_calculate(regr_carrier, flow_rate_carrier)
    flow_voltage_ctrl = MFC_calculate(regr_ctrl, flow_rate_ctrl)
    flow_voltage_odor = MFC_calculate(regr_odor, flow_rate_odor)
    flow_voltage_CO2 = MFC_calculate(regr_CO2, flow_rate_CO2)
    flow_voltage_ctrl2 = MFC_calculate(regr_ctrl2, flow_rate_ctrl2)
    parameters_value_MFC = [flow_voltage_carrier, flow_voltage_ctrl, flow_voltage_odor, flow_voltage_CO2, flow_voltage_ctrl2]
    # parameters_value = [flow_voltage_carrier, flow_voltage_carrier]
    print(parameters_value_MFC)
    # send out the commands
    cmd_MFC.send('flow_setup', *parameters_value_MFC)


def MFC_calculate(model, flow_rate):
    """calculate the voltage value for specified flow rate"""
    return int(model.predict([[flow_rate]]))


def create_valve_entry(frame, text, col=0, row=0, width=8):
    """create an label and text entry"""
    ttk.Label(frame, text=text).grid(column=col, row=row)
    entry1 = ttk.Entry(frame, width=width)
    entry1.grid(column=col + 1, row=row)
    entry2 = ttk.Entry(frame, width=width)
    entry2.grid(column=col + 2, row=row)
    return (entry1, entry2)


def load_valve_txt():
    # clear the existing entries first
    for v in valve_entries:
        valve_entries[v][0].delete(0, tk.END)
        valve_entries[v][1].delete(0, tk.END)
    # pop-up a window asking for file
    valve_file = filedialog.askopenfile(
        filetypes=(("Text File", "*.txt"), ("All Files", "*.*")),
        title="Choose the valve setting file.")
    # fill in entries line-by-line
    for line in valve_file.readlines():
        valve_info = line.rstrip().split(';')
        valve_id = valve_info[0]
        valve_entries[valve_id][0].insert(tk.END, valve_info[1])
        valve_entries[valve_id][1].insert(tk.END, valve_info[2])


def get_valve_info():
    res = ['\nValve']
    for v in all_valves:
        e = [valve_entries[v][i].get() for i in range(2)]
        res.append(':'.join([v] + e))
    print('_'.join(res))


def purge_system():
    """before and after use, purge the entire system"""
    purge_times = int(purge_times_entry.get())
    cmd.send('purge_system', purge_times)
    print('purging the entire system...')


def solvent_wash():
    # reduce the odor stream flow rate
    parameters_value = [200, 20, 200]
    # send out the commands
    cmd_MFC.send('flow_setup', *parameters_value)
    cmd.send('solvent_wash')
    print('doing solvent wash...')


def solvent_dry():
    # increase the flow rate, but flow air only
    parameters_value = [200, 200, 200]
    # send out the commands
    cmd_MFC.send('flow_setup', *parameters_value)
    cmd.send('solvent_wash')
    print('doing solvent dry...')


def switch_panel_manually():
    # switch panel
    cmd.send('switch_panel')


def load_markes_tubes():
    """send GC ready signal to Markes to start loading the tubes
    if need to deliver single odorants, need to trigger that delivery as well"""

    # some setting
    # how many seconds to wait between loading tubes and single odorants
    delay_single = 60 * 1

    # send command to Arduino to trigger Markes to load tubes
    cmd_MFC.send('trigger_markes', 10)
    print('Load Markes tubes at:')
    serial_timestamp(arduino_MFC)

    # deliver single odorant block if specified
    single_block_idx = int(markes_single_odorant_entry.get())
    def load_markes_tubes_callback():
        wait_ms(delay_single * 1000)
        start_loop(True)
    if single_block_idx > 0:
        t6 = threading.Thread(target=load_markes_tubes_callback)
        t6.start()


def open_CO2_valve_thread(delay_duration, co2_duration):
    """start a thread to open the CO2 valve """
    def open_CO2_valve_thread_callback():
        wait_ms(delay_duration * 1000)
        cmd.send('open_CO2_valve', co2_duration * 100)
        print('CO2 valve opened at:', str(datetime.now()))
        return
    t4 = threading.Thread(target=open_CO2_valve_thread_callback)
    t4.start()


def trigger_markes():
    """when Trigger Markes button is pressed, do the following:
    1. send signal to Arduino to close contact between red & white for 30s
        to start trap purge and trap desorption
    2. start a thread of DAQ to listening for yellow & green to time
        when trap fires
    3. send a signal to DAQ to trigger ScanImage
    4. based on the CO2 timing input, calculate when to open the CO2 valve
    5. open the CO2 valve """
    # some setting
    # time between trap fire and odor puff arrives at the mixing manifold, unit sec
    # this could be measured by PID
    time_to_manifold = 3
    # time between start trap purge to trap fire, unit sec
    # this could measured by time difference between GUI command and fire time
    time_to_fire = 23
    # total duration for ScanImage recording, unit is sec
    total_duration = 90

    # start trap purge
    cmd_MFC.send('trigger_markes', 90)
    print('Start pre-fire trap purge at: ', str(datetime.now()))
    # serial_timestamp(arduino_MFC)

    # start the ScanImage trigger
    daq_ttl_thread_simple(total_duration)

    # start CO2
    co2_timing = int(CO2timing_entry.get())
    co2_duration = int(CO2duration_entry.get())
    # time to open the CO2 valve depends on which mode to use
    # for experiments that deliver CO2 prior to human
    if co2_timing > 0:
        daq_ttl_thread_markes()
        delay_duration = time_to_manifold + time_to_fire - co2_timing
        open_CO2_valve_thread(delay_duration, co2_duration)
    # for experiments that deliver CO2 the same time
    elif co2_timing == 0:
        daq_ttl_thread_markes(True, time_to_manifold, co2_duration)
    # no CO2 delivery
    else:
        daq_ttl_thread_markes()

# settings
# DAQ
# 20180918 comment following lines to disable DAQ trigger
dev = 'USB6000/'
# which lines are connected to ScanImage DAQ
start_line = 'pfi0'
stop_line = 'pfi1'
# which line is connected to Markes for monitoring trap firing time
markes_line = 'port0/line2'
daq_task = nidaqmx.Task()
daq_task.do_channels.add_do_chan(dev + start_line)
daq_task.do_channels.add_do_chan(dev + stop_line)
daq_task2 = nidaqmx.Task()
daq_task2.di_channels.add_di_chan(dev + markes_line)
# how many seconds pre and post odor should acquire images for
acquisition_pre = 7
acquisition_post = 20
# for CO2
acquisition_post_co2 = 90
# the ON time for TTL in unit of ms
acquisition_on = 5

# Arduino
# communication port for Arduino
com_valve = 'com6'  # Mega2560 board to control valves
# com_valve = 'com4'
com_MFC = 'com9'    # Uno board to control MFC
# com_MFC = 'com8'
# 20180918 change the com name for use with MacBook
#com_valve = '/dev/cu.usbmodem1411'  # Mega2560 board to control valves
#com_MFC = '/dev/cu.usbmodem1421'    # Uno board to control MFC
arduino_valve = PyCmdMessenger.ArduinoBoard(com_valve, baud_rate=115200)
# arduino = PyCmdMessenger.ArduinoBoard("/dev/cu.usbmodem1441", baud_rate=115200)
commands_valve = [['open_odor_valve', 'ci'],
                  ['switch_panel', ''],
                  ['extra_flush', 'ii'],
                  ['purge_system', 'i'],
                  ['solvent_wash', ''],
                  ['open_CO2_valve', 'i'],
                  ['open_odor_CO2', 'ci']]
# attach commands to Arduino
cmd = PyCmdMessenger.CmdMessenger(arduino_valve, commands_valve)
arduino_MFC = PyCmdMessenger.ArduinoBoard(com_MFC, baud_rate=115200)
commands_MFC = [['flow_setup', 'iiiii'],
                ['trigger_markes', 'i']]
cmd_MFC = PyCmdMessenger.CmdMessenger(arduino_MFC, commands_MFC)


# default flow rates, set as string type
flow_carrier_default = '400'
flow_odor_default = '400'
flow_ctrl_default = '400'
flow_CO2_default = '65'
flow_ctrl2_default = '65'
# MFC calibration data
# x = np.array(range(255, 70, -20))
x = np.array([250, 200, 150, 100, 50])
y_odor = [456, 365, 275, 185, 95]
y_carrier = [914, 731, 548, 365, 184]
y_ctrl = [912, 730, 548, 368, 187]
y_CO2 = [459, 367, 275, 183, 92]
y_ctrl2 = [459, 368, 274, 183, 92]
y_carrier = np.array(y_carrier).reshape(-1, 1)
y_odor = np.array(y_odor).reshape(-1, 1)
y_ctrl = np.array(y_ctrl).reshape(-1, 1)
y_CO2 = np.array(y_CO2).reshape(-1, 1)
y_ctrl2 = np.array(y_ctrl2).reshape(-1, 1)
regr_carrier = linear_model.LinearRegression()
regr_carrier.fit(y_carrier, x)
regr_odor = linear_model.LinearRegression()
regr_odor.fit(y_odor, x)
regr_ctrl = linear_model.LinearRegression()
regr_ctrl.fit(y_ctrl, x)
regr_CO2 = linear_model.LinearRegression()
regr_CO2.fit(y_CO2, x)
regr_ctrl2 = linear_model.LinearRegression()
regr_ctrl2.fit(y_ctrl2, x)

# prepare time between valve open and masterValve open, unit ms
# should be consistent with Arduino board
prepare = 1000


# a global variable to constantly check if 'Stop' button is pressed
global interrupted
interrupted = 0


# GUI design
# window settings
win = tk.Tk()
win.title('Odor Delivery GUI')

# creating main frames
font_big = ('TkDefaultFont', 18, 'bold')
# flow rate frame
frame_flow = tk.LabelFrame(win, text='Flow Control', font=font_big)
frame_flow.grid(column=0, row=1, padx=20, pady=20, sticky=tk.W)
# pattern frame
frame_pattern = tk.LabelFrame(win, text='Odor Pattern', font=font_big)
frame_pattern.grid(column=1, row=0, padx=20, pady=20, sticky=tk.E)
# Valves panel
frame_valve = tk.LabelFrame(win, text='Valve Info', font=font_big)
frame_valve.grid(column=0, row=0, padx=20, pady=20, sticky=tk.W)
# Control panel
frame_control = tk.LabelFrame(win, text='Main Control', font=font_big)
frame_control.grid(column=1, row=1, padx=20, pady=20, sticky=tk.E)

# flow rate frame
ttk.Label(frame_flow, text='Carrier stream:').grid(column=0, row=0)
# set the default value
flow_carrier_entry = ttk.Entry(frame_flow, width=8)
flow_carrier_entry.grid(column=1, row=0)
flow_carrier_entry.insert(tk.END, flow_carrier_default)

ttk.Label(frame_flow, text='Odor stream:').grid(column=2, row=0)
flow_odor_entry = ttk.Entry(frame_flow, width=8)
flow_odor_entry.grid(column=3, row=0)
flow_odor_entry.insert(tk.END, flow_odor_default)

ttk.Label(frame_flow, text='CO2 stream:').grid(column=2, row=1)
flow_CO2_entry = ttk.Entry(frame_flow, width=8)
flow_CO2_entry.grid(column=3, row=1)
flow_CO2_entry.insert(tk.END, flow_CO2_default)

# a button to set up flow rate
button_flow = ttk.Button(frame_flow, text='Setup!', command=flow_setup)
button_flow.grid(column=0, row=2)
# a button to purge the entire system
button_flow = ttk.Button(frame_flow, text='Purge!', command=purge_system)
button_flow.grid(column=0, row=3)
# text entry to specify purge how many times
purge_times_entry = ttk.Entry(frame_flow, width=4)
purge_times_entry.grid(column=1, row=3)
purge_times_entry.insert(tk.END, 1)
# a button to do solvent wash
button_wash = ttk.Button(frame_flow, text='Solvent wash', command=solvent_wash)
button_wash.grid(column=0, row=4)
# a button to do solvent wash
button_dry = ttk.Button(frame_flow, text='Solvent dry', command=solvent_dry)
button_dry.grid(column=0, row=5)

# odor pattern frame
# radio button to choose user-defined or randomly generate
# default is user-defined
pattern_random = tk.BooleanVar(value=False)
radio_user = tk.Radiobutton(frame_pattern, text='User defined',
                            variable=pattern_random, value=False,
                            command=disable_random)
radio_user.grid(column=0, row=0, sticky=tk.W)
# scrolledText to represent the pattern String
num_blocks = 16
pattern_string_entries = []
for ii in range(num_blocks):
    entry_temp = ttk.Entry(frame_pattern, width=30)
    entry_temp.grid(column=2*(ii//8), row=ii%8+1)
    entry_temp.insert(tk.END, 'Z10_A3;1')
    pattern_string_entries.append(entry_temp)
    label_temp = ttk.Label(frame_pattern, text=f'{ii+1}')
    label_temp.grid(column=2*(ii//8)+1, row=ii%8+1)

# if choose randomly generate
radio_random = tk.Radiobutton(frame_pattern, text='Randomly generate',
                              variable=pattern_random, value=True,
                              command=enable_random)
radio_random.grid(column=0, row=num_blocks+2, sticky=tk.W, pady=(15, 0))
# get parameters for random generateion
# odor on duration
ttk.Label(frame_pattern, text='Odor On Duration (s):').grid(column=0, row=num_blocks+3)
random_on_dur_entry = ttk.Entry(frame_pattern, width=4)
random_on_dur_entry.grid(column=1, row=num_blocks+3)
random_on_dur_entry.insert(tk.END, 3)
# odor off duration
ttk.Label(frame_pattern, text='Odor Off Duration (s):').grid(column=0, row=num_blocks+4)
random_off_dur_entry = ttk.Entry(frame_pattern, width=4)
random_off_dur_entry.grid(column=1, row=num_blocks+4)
random_off_dur_entry.insert(tk.END, 60)
# which channels to randomize
ttk.Label(frame_pattern, text='Channels to randomize:').grid(column=0, row=num_blocks+5)
random_channels_entry = ttk.Entry(frame_pattern, width=10)
random_channels_entry.grid(column=1, row=num_blocks+5)
random_channels_entry.insert(tk.END, 'ABCDEFGHIJLMNOPQRSTU')
# open how many times
ttk.Label(frame_pattern, text='Num of puffs each:').grid(column=0, row=num_blocks+6)
num_puffs_entry = ttk.Entry(frame_pattern, width=4)
num_puffs_entry.grid(column=1, row=num_blocks+6)
num_puffs_entry.insert(tk.END, 3)
# click generate button to set the pattern_string
button_generate = ttk.Button(frame_pattern, text='Generate!', command=random_generate)
button_generate.configure(state='disabled')
button_generate.grid(column=0, row=num_blocks+7)

# valve info frame
ttk.Label(frame_valve, text='Name').grid(column=1, row=0)
ttk.Label(frame_valve, text='Conc.').grid(column=2, row=0)
ttk.Label(frame_valve, text='Name').grid(column=5, row=0)
ttk.Label(frame_valve, text='Conc.').grid(column=6, row=0)
# symbol for all valves in two panels
# channel W is the CO2
all_valves = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J',
              'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U']
valve_entries = {}
for i, v in enumerate(all_valves):
    valve_entries[v] = create_valve_entry(frame_valve, v, 4 * (i // 10), i % 10 + 1)
# add a Load button to load valve info from a text file
button_load_valve = tk.Button(frame_valve, text='Load..', command=load_valve_txt)
button_load_valve.grid(column=3, row=12)

# control frame
# Start button
button_start = tk.Button(frame_control, text='Start', command=start_loop)
button_start.grid(column=0, row=0)
# text entry to specify what block to deliver
block_idx_entry = ttk.Entry(frame_control, width=4)
block_idx_entry.grid(column=1, row=0)
block_idx_entry.insert(tk.END, 1)
# Stop button
button_stop = tk.Button(frame_control, text='Stop', command=stop_loop)
button_stop.grid(column=0, row=1)
button_stop.configure(state='disabled')
# a button to start loading Markes tubes
button_tubes = tk.Button(frame_control, text='Start Markes', command=load_markes_tubes)
button_tubes.grid(column=0, row=2)
ttk.Label(frame_control, text='Single odorant block:').grid(column=0, row=3)
markes_single_odorant_entry = ttk.Entry(frame_control, width=4)
markes_single_odorant_entry.grid(column=1, row=3)
markes_single_odorant_entry.insert(tk.END, -1)
# a button to trigger Markes
button_markes = tk.Button(frame_control, text='Trigger Markes', command=trigger_markes)
button_markes.grid(column=0, row=4)
# text entry to specify when CO2 is delivered; 0 means same time; -1 means no CO2
ttk.Label(frame_control, text='CO2 prior(s):').grid(column=0, row=5)
CO2timing_entry = ttk.Entry(frame_control, width=4)
CO2timing_entry.grid(column=1, row=5)
CO2timing_entry.insert(tk.END, -1)
# a text entry to specify CO2 duration
ttk.Label(frame_control, text='CO2 duration(s):').grid(column=0, row=6)
CO2duration_entry = ttk.Entry(frame_control, width=4)
CO2duration_entry.grid(column=1, row=6)
CO2duration_entry.insert(tk.END, 3)


# start mainloop
win.mainloop()
