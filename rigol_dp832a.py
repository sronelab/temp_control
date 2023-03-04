#Class for controlling the linear DC Rigol DP832A
#We will control the voltage to then control the flow valves

import socket
import time
import numpy as np
import time
from Tools import Tools
import os
import json
import Constants

DIRECTORY = os.getcwd() #We want to save our current directory!



#Class to represent/communicate with Rigol DP832A power supply. 3 Channel supply.
#For Sr1 HEPA, CH1 is being used to power 2x valves.
#Ch2 controls Sr1 Chamber HEPA
#Ch3 controls Sr1 table lasers partition
class rigol_dp832a():
    '''Constructor

    Params:
        name: The name of the chiller
        params: Parameter dictionary for initializing Rigol. Must contain "address" parameter with ip address
        log_file: The filename to log the chiller'''


    def __init__(self, name, params):

        self.type = "rigol dp832a"
        self.name = name

        self.setpoint_min = Constants.Constants.VALVE_V_MIN
        self.setpoint_max = Constants.Constants.VALVE_V_MAX
        self.setpoints = [Constants.Constants.VALVE_V_DEFAULT for _ in range(3)]

        self.port = 5555 #default Rigol, not 100 percent sure
        self.ip_address = params["address"]

        self.current_modified_julian_date = int(Tools.get_modified_julian_date())
        self.create_log_file()

        print("Device initialized: " + name)

    '''For compatibility, used to configure specific channels if there is a different min and max voltage for each, for example'''
    def configure_channel(self, channel_number, params):
        pass #TODO this could be implemented later if necessary. For now there's nothing to set but names...

    '''Creates log file for the device'''
    def create_log_file(self):
        log_file_directory = DIRECTORY+"/Logging/"+self.name.replace(" ","")
        try:
            os.mkdir(log_file_directory)
        except OSError: #directory already exists
            pass
        self.log_file = log_file_directory + "/" + str(self.current_modified_julian_date) + ".txt"
        with open(self.log_file, "a"):
            pass #Just create the file
        print("Created log file for device " + self.name)



    '''Writes voltage for a specific channel to the Rigol.
    Params:
        voltage: The voltage to write
        channel: 1, 2, or 3'''
    def write_voltage(self,voltage, channel):

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((self.ip_address, self.port))

            command_channel = ':INST CH' + str(channel) + ' \n' #command to set channel
            command_voltage = ':VOLT ' + str(voltage) +' \n' #command to set voltage on channel
            command_on = ':OUTP CH' + str(channel) + ',ON' + ' \n' #command to set output on channel

            s.send(command_channel)
            time.sleep(.05)
            s.send(command_voltage)
            time.sleep(0.05)
            s.send(command_on)
            time.sleep(0.05)

            self.setpoints[channel - 1] = float(voltage)

        finally:
            s.close()


    '''Sets the setpoint (voltage) of the Rigol.
    Params:
        voltage: The desired setpoint in Volts.
    Returns: whether the setpoint change was successful'''
    def set_setpoint(self, voltage, channel):
        print("Setting Rigol voltage to " + str(voltage) + " on channel " + str(channel))
        channel = int(channel)
        voltage_adjusted = min(max(voltage, self.setpoint_min), self.setpoint_max)
        if voltage != voltage_adjusted:
            print("ERROR: Computed rigol setpoint outside of allowed values")
        rounded_voltage = "%.2f" % voltage_adjusted
        self.write_voltage(rounded_voltage, channel)
        print("Set new setpoint for Rigol channel " + str(channel) + ": " + rounded_voltage) #TODO remove
        return True

    '''Returns the setpoint for a given channel'''
    def get_setpoint(self, channel):
        return self.setpoints[channel - 1]



    '''Sets the voltage output of the Rigol. Equivalent to set_voltage() but
    matches write() method of other devices as an informal interface.'''
    def write(self, voltage, channel):
        self.set_setpoint(voltage, channel)


    '''Close for compatibility - does nothing'''
    def close(self):
        pass

    '''Logs the setpoints of the Rigol, as array [MJD, [ch1, ch2, ch3]]'''
    def log(self):
        if not int(Tools.get_modified_julian_date()) == self.current_modified_julian_date:
            #we crossed midnight
            self.current_modified_julian_date = int(Tools.get_modified_julian_date())
            self.create_log_file()
        with open(self.log_file, "a") as f:
            self.setpoints = [float(s) for s in self.setpoints]
            f.write(json.dumps([Tools.get_modified_julian_date(), self.setpoints])+"\n")
