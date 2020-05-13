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
    parameters_value = []
    # repeats number separate by ;
    pattern_fields = pattern.split(';')
    if len(pattern_fields) == 1:
        repeat = 1
    else:
        repeat = int(pattern_fields[1])
    # odor and CO2 pattern separate by +
    streams = pattern_fields[0].split('+')
    for stream in streams:
        parameters_value_temp = []
        num_channels = 0
        fields = stream.split('_')
        for f in fields:
            valve = f[0]
            if valve == '#':
                # means need to switch the panel
                parameters_value_temp += [valve, 0]
                num_channels += 1
                continue
            # check if the pattern string is valid or not
            if valve not in all_valves + ['Z', 'W']:
                messagebox.showinfo('Error!', 'Pattern String incorrect!')
                return None, None
            duration = int(float(f[1:]) * 100)  # time unit is 10ms
            parameters_value_temp += [valve, duration]
            num_channels += 1
        parameters_value.append([num_channels] + parameters_value_temp)
    parameters_value_final = [repeat]
    # cases where only odor or CO2 is specified, add an empty list
    if len(streams)<2:
        if 'W' in parameters_value[0]:
            parameters_value_final.append([])
            parameters_value_final.append(parameters_value[0])
        else:
            parameters_value_final.append(parameters_value[0])
            parameters_value_final.append([])
    else:
        parameters_value_final += parameters_value
    return parameters_value_final
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


def serial_timestamp(channel_name, arduino):
    """constantly monitor serial, return the timestamp when it's not empty"""
    while(1):
        input = arduino.read()
        if input == b'1':  # get some input from Arduino
            print(channel_name + str(datetime.now()))
            return


def daq_ttl_thread(symbol, duration):
    """generate a square TTL for DAQ line"""
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


def daq_ttl_thread_co2(symbol, duration):
    """generate a square TTL for DAQ line"""
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
        wait_ms(acquisition_pre * 1000 + duration * 10 + acquisition_post_co2 * 1000 - start_take_time)
        print('triggerStop for ' + symbol + ':', end='')
        print(str(datetime.now()))
        daq_task.write([False, True])
        print('>>>>>')
        wait_ms(acquisition_on)
        daq_task.write([False, False])
        return
    t2 = threading.Thread(target=daq_ttl_thread_callback)
    t2.start()


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
    co2_pattern = parameters_value[2]
    def go_through_stream_odor():
        """go through the pattern specified by the odor stream"""
        for num_valve in range(odor_pattern[0]):
            if interrupted:
                break
            idx = 1 + num_valve * 2  # the idx of valve in the pattern list
            valve_symbol = odor_pattern[idx]
            valve_duration = odor_pattern[idx + 1]   # in unit of 10ms)
            if valve_symbol == 'Z':
                # added 20180827: extra flush Control
                [pre_flush_dur, extra_flush_dur] = calculate_flush(valve_duration)
                # [pre_flush_dur, extra_flush_dur] = [300, 2000]  # unit of 10ms
                cmd.send('extra_flush', pre_flush_dur, extra_flush_dur)
                # this a control valve, if next channel is an odor channel
                # need to send DAQ START signal for it
                if num_valve < odor_pattern[0] - 1 and \
                        odor_pattern[idx + 2] in all_valves:
                    # wait ms before start image acquisition
                    wait_ms(valve_duration * 10 - acquisition_pre * 1000)
                    daq_ttl_thread(odor_pattern[idx+2], odor_pattern[idx+3])
                    # wait a little more until send signal to Arduino
                    wait_ms(acquisition_pre * 1000 - acquisition_on - prepare)
                    # print(str(datetime.now()))
                else:
                    # Z is the last channel or next channel is not odor channel
                    # do nothing but wait
                    wait_ms(valve_duration * 10 - prepare)   # in unit of ms
            elif valve_symbol == '#':
                total_switch_dur = 1000  # in unit of 10ms
                [pre_flush_dur, extra_flush_dur] = calculate_flush(total_switch_dur)
                # [pre_flush_dur, extra_flush_dur] = [300, 2000]  # unit of 10ms
                cmd.send('extra_flush', pre_flush_dur, extra_flush_dur)
                print('flushing manifold before switching')
                wait_ms(total_switch_dur * 10 + 3000)  # wait 13s to flush the old manifold
                cmd.send('switch_panel')
                print('switchPanel:' + str(datetime.now()))
                cmd.send('extra_flush', pre_flush_dur, extra_flush_dur)
                print('flushing manifold after switching')
                wait_ms(total_switch_dur * 10 + 3000)  # wait 13s to flush the new manifold
            else:
                # odor valve, send command to Arduino
                # monitor serial and print out timestamp
                # print('channel_' + valve_symbol)
                cmd.send('open_odor_valve', valve_symbol, valve_duration)
                print(valve_symbol+'_send'+str(datetime.now()))
                serial_timestamp(valve_symbol+'_received', arduino_valve)
                serial_timestamp(valve_symbol+'_open', arduino_valve)
                serial_timestamp(valve_symbol+'_closed', arduino_valve)
        print('odor stream finished at', str(datetime.now()))


    def go_through_stream_co2():
        """go throuth the pattern specified by the co2 stream"""
        for num_valve in range(co2_pattern[0]):
            if interrupted:
                break
            idx = 1 + num_valve * 2  # the idx of valve in the pattern list
            valve_symbol = co2_pattern[idx]
            valve_duration = co2_pattern[idx + 1]   # in unit of 10ms
            if valve_symbol == 'Z':
                wait_ms(valve_duration * 10)   # in unit of ms
            else:
                # odor valve, send command to Arduino
                # monitor serial and print out timestamp
                # print('channel_CO2')
                cmd.send('open_CO2_valve', valve_duration)
                print('CO2_send'+str(datetime.now()))
                serial_timestamp('CO2_received', arduino_valve)
                serial_timestamp('CO2_open', arduino_valve)
                serial_timestamp('CO2_closed', arduino_valve)
        print('co2 stream finished at', str(datetime.now()))

    def go_through_pattern_callback():
        for r in range(num_repeat):
            if odor_pattern:
                t2 = threading.Thread(target=go_through_stream_odor)
                t2.start()
            if co2_pattern:
                t3 = threading.Thread(target=go_through_stream_co2)
                t3.start()
            # loop is finished, reset the Start and Stop button and flag
            when_interrupted()
            return

    # use a new thread, to avoid freezing the GUI
    t1 = threading.Thread(target=go_through_pattern_callback)
    t1.start()


def start_loop():
    """start the delivery pattern loop"""
    # parse the odor pattern to get parameter types and values
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
    flow_rate_ctrl = int(flow_ctrl_entry.get())
    flow_rate_odor = int(flow_odor_entry.get())
    flow_rate_CO2 = int(flow_CO2_entry.get())
    flow_voltage_carrier = MFC_calculate(regr_carrier, flow_rate_carrier)
    flow_voltage_ctrl = MFC_calculate(regr_ctrl, flow_rate_ctrl)
    flow_voltage_odor = MFC_calculate(regr_odor, flow_rate_odor)
    flow_voltage_CO2 = MFC_calculate(regr_CO2, flow_rate_CO2)
    parameters_value_MFC = [flow_voltage_carrier, flow_voltage_ctrl, flow_voltage_odor, flow_voltage_CO2]
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


# settings
# DAQ
# 20180918 comment following lines to disable DAQ trigger
dev = 'USB6000/'
# which lines are connected to ScanImage DAQ
start_line = 'pfi0'
stop_line = 'pfi1'
daq_task = nidaqmx.Task()
daq_task.do_channels.add_do_chan(dev + start_line)
daq_task.do_channels.add_do_chan(dev + stop_line)
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
com_MFC = 'com5'    # Uno board to control MFC
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
                  ['open_CO2_valve', 'i']]
# attach commands to Arduino
cmd = PyCmdMessenger.CmdMessenger(arduino_valve, commands_valve)
arduino_MFC = PyCmdMessenger.ArduinoBoard(com_MFC, baud_rate=115200)
commands_MFC = [['flow_setup', 'iiii']]
cmd_MFC = PyCmdMessenger.CmdMessenger(arduino_MFC, commands_MFC)


# default flow rates, set as string type
flow_carrier_default = '400'
flow_odor_default = '400'
flow_ctrl_default = '400'
flow_CO2_default = '100'
# MFC calibration data
# x = np.array(range(255, 70, -20))
x = np.array([250, 200, 150, 100, 50])
y_carrier = [895, 717, 539, 361, 182, ]
y_odor = [447, 358, 270, 181, 93]
y_ctrl = [448, 358, 269, 179, 90]
y_CO2 = [893, 715, 536, 357, 179]
y_carrier = np.array(y_carrier).reshape(-1, 1)
y_odor = np.array(y_odor).reshape(-1, 1)
y_ctrl = np.array(y_ctrl).reshape(-1, 1)
y_CO2 = np.array(y_CO2).reshape(-1, 1)
regr_carrier = linear_model.LinearRegression()
regr_carrier.fit(y_carrier, x)
regr_odor = linear_model.LinearRegression()
regr_odor.fit(y_odor, x)
regr_ctrl = linear_model.LinearRegression()
regr_ctrl.fit(y_ctrl, x)
regr_CO2 = linear_model.LinearRegression()
regr_CO2.fit(y_CO2, x)

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

ttk.Label(frame_flow, text='Ctrl stream:').grid(column=0, row=1)
flow_ctrl_entry = ttk.Entry(frame_flow, width=8)
flow_ctrl_entry.grid(column=1, row=1)
flow_ctrl_entry.insert(tk.END, flow_ctrl_default)

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
    entry_temp.insert(tk.END, 'Z10_A3+Z10_W3;1')
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
# a button to switch panel manually
button_stop = tk.Button(frame_control, text='Switch Panel', command=switch_panel_manually)
button_stop.grid(column=0, row=2)

# start mainloop
win.mainloop()
