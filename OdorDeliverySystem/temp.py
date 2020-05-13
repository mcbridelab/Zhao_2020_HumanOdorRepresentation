def go_through_pattern(arduino, cmd, parameters_value):
    """go through the odor delivery pattern in a separate thread"""
    # print(parameters_value)
    def go_through_pattern_callback():
        for num_valve in range(parameters_value[0]):
            if interrupted:
                break
            idx = 1 + num_valve * 2  # the idx of valve in the pattern list
            valve_symbol = parameters_value[idx]
            valve_duration = parameters_value[idx + 1]   # in unit of 10ms)
            if valve_symbol == 'Z':
                # added 20180827: extra flush Control
                [pre_flush_dur, extra_flush_dur] = calculate_flush(valve_duration)
                # [pre_flush_dur, extra_flush_dur] = [300, 2000]  # unit of 10ms
                cmd.send('extra_flush', pre_flush_dur, extra_flush_dur)
                # this a control valve, if next channel is an odor channel
                # need to send DAQ START signal for it
                if num_valve < parameters_value[0] - 1 and \
                        parameters_value[idx + 2] in all_valves+['W']:
                    # wait ms before start image acquisition
                    wait_ms(valve_duration * 10 - acquisition_pre * 1000)
                    # send the start signal and print timestamp
                    # daq_ttl(start_line)
                    # print('triggerStart for ' + parameters_value[idx+2] + \
                    # ": " + str(datetime.now()))
                    # start a new thread in order to send DAQ STOP signal
                    # 20180918 comment this line to disable trigger
                    daq_ttl_thread(parameters_value[idx+2], parameters_value[idx+3])
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
            elif valve_symbol == 'W': # if it's CO2 valve
                # adjust the flow rate for MFC
                flow_rate_carrier = int(flow_carrier_entry.get())
                flow_rate_ctrl = int(flow_ctrl_entry.get())
                flow_rate_odor = int(flow_odor_entry.get())
                flow_rate_CO2 = int(flow_CO2_entry.get())
                # flow rate: carrier_new + CO2 = carrier_old + ctrl
                # ctrl_new = CO2
                flow_rate_carrier_new = flow_rate_carrier + flow_rate_ctrl - flow_rate_CO2
                # calculate corresponding voltage
                flow_voltage_carrier = MFC_calculate(regr_carrier, flow_rate_carrier)
                flow_voltage_carrier_new = MFC_calculate(regr_carrier, flow_rate_carrier_new)
                flow_voltage_ctrl = MFC_calculate(regr_ctrl, flow_rate_ctrl)
                flow_voltage_ctrl_new = MFC_calculate(regr_ctrl, flow_rate_CO2)
                flow_voltage_odor = MFC_calculate(regr_odor, flow_rate_odor)
                flow_voltage_CO2 = MFC_calculate(regr_CO2, flow_rate_CO2)
                parameters_value_MFC = [flow_voltage_carrier_new, flow_voltage_ctrl_new, flow_voltage_odor, flow_voltage_CO2]
                # parameters_value = [flow_voltage_carrier, flow_voltage_carrier]
                print(parameters_value_MFC)
                # send out the commands
                cmd_MFC.send('flow_setup', *parameters_value_MFC)
                # wait a few seconds for MFC to reach set values
                wait_ms(20 * 1000)
                # then open the CO2 valve
                print('channel_' + valve_symbol)
                cmd.send('open_CO2_valve', valve_duration)
                print(str(datetime.now()))
                serial_timestamp(arduino_valve)
                serial_timestamp(arduino_valve)
                serial_timestamp(arduino_valve)
                # wait 60 sec until the Markes finish, before set the flow rate back
                wait_ms(60 * 1000)
                parameters_value_MFC = [flow_voltage_carrier, flow_voltage_ctrl, flow_voltage_odor, flow_voltage_CO2]
                print(parameters_value_MFC)
                # send out the commands
                cmd_MFC.send('flow_setup', *parameters_value_MFC)
            else:
                # odor valve, send command to Arduino
                # monitor serial and print out timestamp
                print('channel_' + valve_symbol)
                cmd.send('open_odor_valve', valve_symbol, valve_duration)
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
