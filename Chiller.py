import serial
from Tools import Tools
import os
import json
import Constants

DIRECTORY = os.getcwd() #We want to save our current directory!


'''Class representing and communicating with a chiller.'''
class Chiller():

    '''Constructor

    Params:
        name: The name of the chiller
        params: Dictionary of parameters passed from parsing config file. Must include "address" for serial port'''
    def __init__(self, name, params):

        self.type = "chiller"
        self.name = name
        port = params["address"].replace("usb", "USB")
        try:
            self.serial = serial.Serial(port, timeout = .1,
                                        baudrate = 19200)  # open serial port
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
        except serial.SerialException as e:
            print("ERROR unable to connect to chiller " + name)
            raise e
        self.current_modified_julian_date = int(Tools.get_modified_julian_date())
        self.create_log_file()
        self.setpoint_min = Constants.Constants.CHILLER_MIN #degrees C
        self.setpoint_max = Constants.Constants.CHILLER_MAX
        self.setpoint = Constants.Constants.DEFAULT_CHILLER_SETPOINT #starting value, near room temp
        self.water_temp = Constants.Constants.DEFAULT_CHILLER_SETPOINT #starting default value
        self.turn_on()
        print("Device initialized: " + name)

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

    '''Writes a command using a handshake protocol.
    Params:
        command: The command to write
    Returns: whether the write was successful'''
    def write_command_with_handshake(self, command):
        if not command[-1] == '\r':
            command = command + '\r'
        for count in range(Constants.Constants.MAX_TRIALS_CHILLER):
            try:
                self.serial.write(command)
                if self.serial.read(3) == "OK\r":
                    return True
            except Exception:
                pass #Try again
        print("ERROR unable to write command to chiller " + self.name)
        return False

    '''Turns on the chiller'''
    def turn_on(self):
        if not self.write_command_with_handshake("SO 1"):
            raise serial.SerialException("Could not turn on chiller " + self.name)

    '''Turns off the chiller'''
    def turn_off(self):
        if not self.write_command_with_handshake("SO 0"):
            raise serial.SerialException("Could not turn off chiller " + self.name)

    '''Returns the setpoint'''
    def get_setpoint(self, channel = 0):
        return self.setpoint

    '''Sets the setpoint of the chiller.
    Params:
        temp: The desired setpoint
        channel: A dummy variable that isn't useful but is included for interfacing
    Returns: whether the setpoint change was successful'''
    def set_setpoint(self, temp, channel = 0):
        temp_adjusted = min(max(temp, self.setpoint_min), self.setpoint_max)
        if temp != temp_adjusted:
            print("ERROR: Computed chiller setpoint outside of allowed values")
        rounded_temp = "%.2f" % temp_adjusted
        rounded_current_setpoint = "%.2f" % self.setpoint
        if rounded_temp != rounded_current_setpoint:
            self.setpoint = temp_adjusted
            #if not self.write_command_with_handshake("SS " + rounded_temp + "C", "RS", rounded_temp+"C"): ## TODO:
            if not self.write_command_with_handshake("SS " + rounded_temp + "C"):
                print("Error: could not write setpoint to chiller " + self.name)
                return False
        print("Set new setpoint for chiller " + self.name + ": " + rounded_temp) #TODO remove
        return True

    '''Reads the water temp from the chiller'''
    def get_water_temp(self):
        BYTES_TO_READ = 6 #Bytes to read (3 digit temp + decimal point + C + \r)
        for _ in range(Constants.Constants.MAX_TRIALS_CHILLER):
            self.serial.write("RT\r")
            returned_string = self.serial.read(BYTES_TO_READ)
            if len(returned_string) == BYTES_TO_READ: #test if we got complete string
                try:
                    self.water_temp = float(returned_string.strip("C\r"))
                    return self.water_temp
                except ValueError:
                    pass #Invalid string, try again
        print("ERROR cannot read water temperature from chiller")
        return self.water_temp

    '''Closes the chiller (namely its serial port) and sets it back to default temp'''
    def close(self):
        self.set_setpoint(Constants.Constants.DEFAULT_CHILLER_SETPOINT)
        print("Reset " + self.name + " to default setpoint")
        self.serial.close()

    '''Sets the setpoint in the chiller. Equivalent to set_setpoint() but
    matches write() method of other devices as an informal interface.'''
    def write(self, temp, channel = 0):
        self.set_setpoint(temp)

    '''Logs the setpoint and current water temperature in the chiller.'''
    def log(self):
        if not int(Tools.get_modified_julian_date()) == self.current_modified_julian_date:
            #we crossed midnight
            self.current_modified_julian_date = int(Tools.get_modified_julian_date())
            self.create_log_file()
        water_temp = float(self.get_water_temp())
        with open(self.log_file, "a") as f:
            f.write(json.dumps([Tools.get_modified_julian_date(), [float(self.setpoint), water_temp]])+"\n")
