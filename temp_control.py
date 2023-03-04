'''Script for running temperature control servos.

@author Josie Meyer, josephine.meyer@colorado.edu'''

from __future__ import division, print_function
import numpy as np
import time
import threading
import os
from datetime import datetime
import socket
import serial
import struct
import json
import astropy.time

#Get better performance by optimizing range functions in Python 2, 3
try:
    range = xrange
except NameError:
    pass

DIRECTORY = os.getcwd() #We want to save our current directory!


'''Class corresponding to a particular Keithley DMM.'''
class Keithley_DMM():

    #This is extended and modified from the old keithley class in Keithley.py

    NUM_CHANNELS = 40

    '''Initializes the Keithley.
    Params:
        name: A unique name identifying the Keithley
        ip_address: The IP address of the Keithley
        log_file: The file where logging data is to be stored. If None, creates
        a file with default name.'''
    def __init__(self, name, ip_address):
        self.port = 1394 #2701 port
        self.buffer_size=2048
        self.ip_address = ip_address
        self.name = name
        self.type = "keithley"
        self.resistance_25C = np.full(self.NUM_CHANNELS, np.inf) #resistances of thermistors at 25C
        self.beta = np.zeros(self.NUM_CHANNELS) #beta for each thermistor
        self.resistances = np.full(self.NUM_CHANNELS, np.inf) #actual resistances stored in memory
        self.temps = np.full(self.NUM_CHANNELS, -np.inf) #actual temps stored in memo
        self.offset = np.zeros(self.NUM_CHANNELS) #offsets of a few ohms due to cables etc
        self.channel_names = ["" for i in range(40)] #channel names
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.ip_address, self.port))
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.current_modified_julian_date = int(Tools.get_modified_julian_date())
        log_file_directory = DIRECTORY+"/"+self.name.replace(" ", "")
        self.create_log_file()
        print("Device initialized: " + name)

    '''Creates log file for the Keithley'''
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

    '''Reads resistance from a specific channel on the Keithley. Adjusts
    for calibration and converts to temperature.
    Params:
        Channel: The channel number on the Keithley
    Returns: The temperature in degrees celcius
        '''
    def read(self):
        self.resistances = self.read_resistances()
        self.temps = Tools.resistance_to_temp_array(self.resistances, self.resistance_25C, self.beta)

    '''Gets the resistance for a given channel'''
    def get_resistance(self, channel):
        return self.resistances[Tools.channel_number_to_array_index(channel)]

    '''Gets the temp for a given channel'''
    def get_temp(self, channel):
        return self.temps[Tools.channel_number_to_array_index(channel)]

    '''Reads resistances from the Keithley.
    Returns: A length-40 numpy array containing the resistances of all channels.'''
    def read_resistances(self):
        try:
            return np.array(self.read_data_from_card(self.sock, 101, 220))
        except ValueError as e:
            print(e.message + " (If occasional, ignore this error)")
            print("Using cached resistances")
            return self.resistances


        '''Directly queries the card and extracts the resistances from the data.

    Params:
        sock: The socket to communicate with the card
        channel_min: The minimum channel number to query (101 or 201)
        channel_max: The maximum channel number to query (120 or 220)

    Returns: a length-40 numpy array containing the resistances of the channels'''
    def read_data_from_card(self, sock, channel_min, channel_max):
        sock.send("*RST \n") #Resets Keithley
        sock.send("FUNC 'RES',(@{cmin}:{cmax}) \n".format(cmin=str(channel_min), cmax=str(channel_max)))
        sock.send("RES:RANG 1e5 \n")

        sock.send("RES:NPLC 1,(@{cmin}:{cmax}) \n".format(cmin=str(channel_min), cmax=str(channel_max)))
        sock.send("SYST:AZER OFF \n")
        #5 is slow 1 is medium .1 is fast #.05 seems fastest! But as 12.15sec still far too long
        sock.send("TRAC:CLE \n") #Clear buffer
        sock.send("INIT:CONT OFF \n")
        sock.send("TRIG:SOUR IMM \n")
        sock.send("TRIG:COUN 1\n")
        sock.send("SAMP:COUN 40\n")
        sock.send("TRIG:DEL 0\n") #.0005
        sock.send("ROUT:SCAN (@{cmin}:{cmax}) \n".format(cmin=str(channel_min), cmax=str(channel_max)))
        #Sets scan route 1 to 20 here

        sock.send("ROUT:SCAN:TSO IMM \n")
        sock.send("ROUT:SCAN:LSEL INT \n")
        sock.send("READ? \n")
        data = str(sock.recv(self.buffer_size)).strip().split(',')
        if len(data) < 40*3 : #we got no or incomplete data
            if len(data) <= 1: #we got an empty string
                raise ValueError("ERROR: no data received from Keithley")
            raise ValueError("ERROR: incomplete data received from Keithley")
        resistances = []
        for i in range(0, 40):
            resistance = float(data[i*3].strip('OHM'))
            if resistance > 1E7: #Open circuit
                resistance = np.inf
            resistances.append(resistance)
        return np.array(resistances)

    '''Configures a channel on the DMM.'''
    def configure_channel(self, channel_number, name, resistance_25C, beta,
                          offset = 0):
        index = Tools.channel_number_to_array_index(channel_number)
        self.channel_names[index] = name
        self.resistance_25C[index] = resistance_25C
        self.beta[index] = beta
        self.offset[index] = offset

    '''Logs the current time, followed by data stored in the Keithley object'''
    def log(self):
        current_mjd = Tools.get_modified_julian_date()
        if int(current_mjd) != self.current_modified_julian_date: #we've crossed midnight
            self.current_modified_julian_date = int(current_mjd) #update julian date
            self.create_log_file()
        with open(self.log_file, "a") as f:
            f.write(json.dumps([Tools.get_modified_julian_date(), self.temps.tolist()])+"\n")

    '''Closes the device by closing its socket.'''
    def close(self):
        self.sock.close()

class Rigol():
    #TODO implement this class

    def __init__(self, name, ip_address):
        self.name = name
        self.type = "rigol"
        self.ip_address = ip_address

    def set_voltage(self, voltage):
        pass

    def close(self):
        pass

    '''Boilerplate redundant method to set_voltage. Allows for matching
    syntax with chiller.'''
    def write(self, voltage):
        self.set_voltage(voltage)


'''Class representing and communicating with a chiller.'''
class Chiller():

    '''Constructor

    Params:
        name: The name of the chiller
        port: The name of the serial port
        log_file: The filename to log the chiller'''
    def __init__(self, name, port):
        self.type = "chiller"
        self.name = name
        port = port.replace("usb", "USB")
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
        self.setpoint_min = Constants.CHILLER_MIN #degrees C
        self.setpoint_max = Constants.CHILLER_MAX
        self.setpoint = Constants.DEFAULT_CHILLER_SETPOINT #starting value, near room temp
        self.water_temp = Constants.DEFAULT_CHILLER_SETPOINT #starting default value
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
        for count in range(Constants.MAX_TRIALS_CHILLER):
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

    '''Sets the setpoint of the chiller.
    Params:
        temp: The desired setpoint
    Returns: whether the setpoint change was successful'''
    def set_setpoint(self, temp):
        temp_adjusted = min(max(temp, self.setpoint_min), self.setpoint_max)
        if temp != temp_adjusted:
            print("ERROR: Computed chiller setpoint outside of allowed values")
        rounded_temp = "%.1f" % temp_adjusted
        rounded_current_setpoint = "%.1f" % self.setpoint
        if rounded_temp != rounded_current_setpoint:
            self.setpoint = temp_adjusted
            #if not self.write_command_with_handshake("SS " + rounded_temp + "C", "RS", rounded_temp+"C"): ## TODO:
            if not self.write_command_with_handshake("SS " + rounded_temp + "C"):
                print("Error: could not write setpoint to chiller " + self.name)
                return False
        print("Set new setpoint: " + rounded_temp) #TODO remove
        return True

    '''Reads the water temp from the chiller'''
    def get_water_temp(self):
        BYTES_TO_READ = 6 #Bytes to read (3 digit temp + decimal point + C + \r)
        for _ in range(Constants.MAX_TRIALS_CHILLER):
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
        self.set_setpoint(Constants.DEFAULT_CHILLER_SETPOINT)
        print("Reset " + self.name + " to default setpoint")
        self.serial.close()

    '''Sets the setpoint in the chiller. Equivalent to set_setpoint() but
    matches write() method of other devices as an informal interface.'''
    def write(self, temp):
        self.set_setpoint(temp)

    '''Logs the setpoint and current water temperature in the chiller.'''
    def log(self):
        if not int(Tools.get_modified_julian_date()) == self.current_modified_julian_date:
            #we crossed midnight
            self.current_modified_julian_date = int(Tools.get_modified_julian_date())
            self.create_log_file()
        water_temp = self.get_water_temp()
        with open(self.log_file, "a") as f:
            f.write(json.dumps([Tools.get_modified_julian_date(), self.setpoint, water_temp])+"\n")


'''Class corresponding to a particular servo loop. You should have no need
to instantiate this class directly; the Servo_Master class does all of this'''
class Servo:

    '''Instantiates the servo loop.

    Parameters:
        name: The name of the servo loop
        k_prop: Proportional gain coefficient
        t_int: Integration time (~RC time constant) k_int = k_prop/t_int
        t_diff: Differentiation time (~RC time constant) k_diff = k_prop*t_prop
        keithley: The Keithley DMM object whose channels are used in the servo
        input_channels: Either a single channel to read, or a list of channel
            numbers to average their readings
        output_device: The object corresponding to the output device
        setpoint: The setpoint of the control variable
        timestep: How often to refresh the control loop (sec)
        master: the Servo_Master object'''
    def __init__(self, name, k_prop, t_int, t_diff, keithley, input_channel,
                 output_device, setpoint, output_min,
                 output_max, master):
        self.name = name
        self.k = k_prop
        self.t_int = t_int
        self.t_diff = t_diff
        self.keithley = keithley
        self.input_channel = input_channel
        self.output_device = output_device
        self.setpoint = setpoint
        self.integral_value = 0
        self.current_reading = -np.inf
        self.previous_reading = -np.inf
        self.master = master
        self.output_min = output_min
        self.output_max = output_max

    '''Resets numerical parameters in the servo loop without clearing memory.

    Params:
        k_prop: Proportional gain coefficient
        t_int: Integration time
        t_diff: Differentiation time
        setpoint: The setpoint of the control variable
        timestep: How often to refresh the control loop (sec)'''
    def refresh_parameters(self, k_prop, t_int, t_diff, setpoint,
                           output_min, output_max):
        self.k = k_prop
        self.t_int = t_int
        self.t_diff = t_diff
        self.setpoint = setpoint
        self.output_min = output_min
        self.output_max = output_max
        print("Refreshed parameters for servo " + self.name)

    '''Clears the accumulated value on the integrator. The main reason you
    would want to call this is in case of severe integrator windup.'''
    def reset_integrator(self):
        self.integral_value = 0
        print("Reset integrator for servo " + self.name)

    '''Calculates and returns the error signal'''
    def error_signal(self):
        return self.setpoint - self.current_reading

    '''Calculates and returns the output signal'''
    def output_signal(self):
        error = self.error_signal()
        prop = self.k * error
        integral = self.k * self.integral_value
        diff = self.k * (self.previous_reading - self.current_reading) * self.t_diff / Constants.BASE_TICK_INTERVAL
        return prop+integral+diff

    '''Performs one iteration of the servo loop.'''
    def update(self):
        self.previous_reading = self.current_reading
        self.current_reading = self.keithley.get_temp(self.input_channel)
        if (self.previous_reading != -np.inf and self.current_reading != -np.inf): #Avoid error on startup
            self.integral_value += self.error_signal() * Constants.BASE_TICK_INTERVAL / self.t_int
            output = self.output_signal() + self.output_device.setpoint
            control_var = min(max(output, self.output_min), self.output_max)
            if control_var != output: #TODO make sure there are no bugs
                print("ERROR: tried to write control variable outside limits")
            try:
                self.output_device.write(control_var)
            except Exception as e:
                print(e)
                print("ERROR: Unable to write value to device " + self.output_device.name)


'''Auxiliary timer class that controls timing via an external thread.'''
class Aux_Timer(threading.Thread):

    '''Initialized the timer thread. Tells the main thread when to update the
    servo loops and when to refresh the servo loop parameters.
    Params:
       Tick_interval: How often the clock should tick.
       Refresh_interval: How often the refresh flag should be set.
       Clock_flag: An Event object that relays when the clock ticks.
    '''
    def __init__(self, tick_interval,
                 clock_flag):
        threading.Thread.__init__(self) #Must call this for the thread to be set up correctly
        self.tick_interval = tick_interval
        self.clock_flag = clock_flag
        self.daemon = True #it will kill automatically, don't have to worry about zombies

    '''Run method for the timer thread. Infinite loop that sets the refresh
    and servo flags as necessary until timer is killed.'''
    def run(self):
        while True:
            self.clock_flag.set()
            time.sleep(self.tick_interval)


'''The "Master" class that controls all the temperature servos! This is the
class that will be instantiated directly from the script'''
class Servo_Master():

    '''Automatically initializes the class.
    Params:
        config_filename: The filename/path to find the config file'''
    def __init__(self, config_filename):
        self.config_filename = config_filename
        self.file_last_modified = Tools.when_last_modified(config_filename)
        self.servos = {}
        self.devices = {}
        self.current_keithley = "" #ignore, for implementation only
        self.parse_config_file(config_filename)
        self.clock_flag = threading.Event()
        self.timer = Aux_Timer(Constants.BASE_TICK_INTERVAL,
                               self.clock_flag)
        print("Servos initialized")

    '''Refreshes by rereading from file.'''
    def refresh(self):
        self.parse_config_file(self.config_filename)

    '''Returns whether the config file has changed since last refresh.'''
    def config_file_has_changed(self):
        modification_time = Tools.when_last_modified(self.config_filename)
        if modification_time != self.file_last_modified:
            self.file_last_modified = modification_time
            print("Change detected in config file -- recalibrating")
            return True
        return False

    '''Parses the config file to set up instruments and servo loops'''
    def parse_config_file(self, config_filename):
        title = ""
        with open(config_filename) as f:
            for line in f:
                tokens = self.tokenize_line(line)
                if len(tokens) == 1 and tokens[0][-1] == ":": #title
                    title = tokens[0][:-1]
                else:
                    if title and tokens:
                        self.interpret_tokens(tokens, title)

    '''Tokenizes line from the config file'''
    def tokenize_line(self, line):
        return LineTokenizer.tokenize_line(line)

    '''Interprets tokens from the config file.

    Params:
        tokens: Tokens from calling tokenize_line() on a line of config file
        title: The title/heading of the tokenized line within the config file'''
    def interpret_tokens(self, tokens, title):
        if not title:
            raise ValueError("ERROR: No title")
        elif title == "devices":
            self.create_device_from_tokens(tokens)
        elif title == "keithleychannels":
            if len(tokens) == 1: #We have the name of a Keithley
                self.current_keithley = tokens[0]
            elif not self.current_keithley in self.devices:
                raise ValueError("ERROR: Invalid Keithley name: " + self.current_keithley)
                #We don't have a valid Keithley name, or might have empty string if not initialized at all
            else:
                self.configure_channel_from_tokens(tokens, self.current_keithley)
        elif title == "servos":
            self.configure_servo_from_tokens(tokens)
        else:
            raise ValueError("ERROR: Invalid title in config file: " + title)


    '''Configures a device from tokens extracted from the config file.
    Prints an error message but does not propagate exceptions if device
    configuration fails.

    Params:
        tokens: Tokens from the config file'''
    def create_device_from_tokens(self, tokens):
        if len(tokens) != 3: #Too many or too few arguments for a device
            raise ValueError("ERROR: Invalid device info in config file")
        name = tokens[0]
        if name in self.devices: #Check if we already have the device
            return #We already have the device initialized
        #Either the device hasn't been initialized yet, or has changed
        if tokens[1] == "rigol":
            try:
                self.devices[name] = Rigol(name, tokens[2])
            except Exception as e:
                print("ERROR: Unable to initialize Rigol: " + name)
                raise(e)
        elif tokens[1] == "chiller":
            try:
                self.devices[name] = Chiller(name, tokens[2])
            except Exception as e:
                print("ERROR: Unable to initialize chiller: " + name)
                raise(e)
        elif tokens[1] == "keithley":
            try:
                self.devices[name] = Keithley_DMM(name, tokens[2])
            finally:
                pass #TODO
#            except Exception as e:
#                print("ERROR: Unable to initialize Keithley: " + name)
#                raise(e)
        else: #We have an unrecognized device type:
            print("ERROR: Unrecognized device type: " + tokens[1])
            raise ValueError("Unrecognized device type")

    '''Configures a channel from tokens extracted from the config file.
    Prints an error message but does not propagate exceptions.

    Params:
        tokens: Tokens from the config file'''
    def configure_channel_from_tokens(self, tokens, device_name):
        try:
            channel_number = int(tokens[0])
            channel_name = tokens[1]
            calibration = float(tokens[2])
            if len(tokens) <= 3:
                offset = 0
            else:
                offset = float(tokens[3])
            self.devices[device_name].configure_channel(channel_number,
                        channel_name, calibration, offset)
        except Exception as e:
            print(e)
            print("ERROR: Unable to configure channel")


    '''Configures a servo loop from tokens extracted from the config file.
    Prints an error message but does not propagate exceptions if a servo loop
    cannot be constructed.

    Params:
        tokens: Tokens from the config file'''
    def configure_servo_from_tokens(self, tokens):
        try:
            name = tokens[0]
            keithley_name = tokens[1]
            if not keithley_name in self.devices:
                raise ValueError("ERROR: Unrecognized Keithley: " + keithley_name)
            keithley = self.devices[keithley_name]
            thermistor_number = int(tokens[2])
            device_name = tokens[3]
            if not device_name in self.devices:
                raise ValueError("ERROR: Unrecognized device: " + device_name)
            device = self.devices[device_name]
            setpoint = float(tokens[4])
            k = float(tokens[5])
            t_int = float(tokens[6])
            t_diff = float(tokens[7])
            output_min = float(tokens[8])
            output_max = float(tokens[9])
            if name in self.servos and keithley == self.servos[name].keithley and thermistor_number == self.servos[name].input_channel:
                self.servos[name].refresh_parameters(k, t_int,
                           t_diff, setpoint, output_min, output_max)
            else:
                self.servos[name] = Servo(name, k, t_int, t_diff, keithley,
                           thermistor_number, device, setpoint,
                           output_min, output_max, self)
        finally:# TODO
            pass

    '''Starts and runs the servo loops.'''
    def start(self):
        print("Starting logging and servo loops")
        self.timer.start()
        try:
            self.run()
        finally: #Clean up resources
            print("\nClosing program")
            for device in self.devices.values():
                device.close()
                print("Closed device: " + device.name)
            print("Program exited")

    '''Updates the servo loops operated by the servo master object.'''
    def update_servos(self):
        servos = self.servos.values()
        if servos: #Only print if we actually have any servos
            for servo in servos:
                servo.update()
            print("Updated servos")

    '''Initiates logging in all devices that support it. Devices are responsible
    for their own implementation of log.'''
    def log_all(self):
        for device in self.devices.values():
            if hasattr(device, "log"):
                device.log()
        print("Logged all devices")

    '''Main infinite loop that runs the servo loop. Called by start() in new
    thread.'''
    def run(self):
        logging_freq = Constants.LOGGING_INTERVAL // Constants.BASE_TICK_INTERVAL
        logging_count = -1 #We want it to log the second time through loop!
        start_time = time.time()
        while True:
            while not self.clock_flag.isSet():
                self.clock_flag.wait(1) #1 second timeout to catch KeyboardInterrupt
            print("Time: ", time.time() - start_time)
            self.clock_flag.clear() #Reset the event flag to False
            self.update_servos()
            if logging_count == 0:
                self.log_all()
            logging_count = (logging_count + 1) % logging_freq
            if self.config_file_has_changed():
                self.refresh()
                print("Loop parameters updated successfully.")
            for device in self.devices.values():
                if isinstance(device, Keithley_DMM):
                    device.read()

class LineTokenizer:

        '''Parses a line of the file into useful tokens. A complicated function
        that more or less takes in a line from the config file and breaks it into
        parts the rest of the program understands. Deletes comments, whitespace.

        Params:
            line: A line of text from the config file
        Returns: A list of arguments contained in the line.
        If the line is invalid or pure whitespace, returns an empty list.'''
        @staticmethod
        def tokenize_line(line):
            if line is None:
                return []
            line = line.strip().lower()
            if line == "":
                return [] #our line is pure whitespace
            hash_position = line.find('#')
            if hash_position == 0:
                return [] #pure comment
            elif hash_position > 0: #there is a hash, but it isn't first character
                line = line[:hash_position]
            raw_tokens = line.split() #use first pass with Python's tokenizer, then clean up
            tokens = []
            in_quote = False
            in_brackets = False
            current_token = ""
            current_list = []
            for token in raw_tokens: #this is all quote mark and bracket handling!
                if in_quote:
                    if token[-1] == '"':
                        in_quote = False
                        tokens.append(current_token + " " + token[:-1])
                        current_token = ""
                    else:
                        current_token += (" " + token)
                elif in_brackets: #assume we only have channel numbers in brackets
                    if token[-1] == "]":
                        in_brackets = False
                        current_list.append(token[:-1].strip(","))
                        tokens.append(current_list)
                        current_list = ""
                    else:
                        current_list.append(token.strip(","))
                else:
                    if token[0] == '"':
                        in_quote = True
                        current_token = token[1:]
                    elif token[0] == "[":
                        in_brackets = True
                        current_list.append(token[1:].strip(","))
                    else:
                        tokens.append(token)
            if tokens and tokens[-1][-1] == ":": #check if we have a title
                tokens[-1] = tokens[-1]
                new_title = ""
                for token in tokens:
                    new_title += token
                return [new_title]
            return tokens

'''Class containing various exportable constants'''
class Constants:
    #Constants
    BASE_TICK_INTERVAL = 60 #how often clock ticks to update servos (sec)
    LOGGING_INTERVAL = 60 #How often to log (sec)
    MAX_TRIALS_CHILLER = 5 #How many tries to communicate with chiller before giving up
    KELVINS_TO_CELCIUS = 273.15
    DEFAULT_CHILLER_SETPOINT = 21
    CHILLER_MAX = 50 #Maximum allowed setpoint, default
    CHILLER_MIN = 10 #Minimum allowed setpoint, default

'''Class containing various utility functions'''
class Tools:

    '''Helper function that gets and returns a string representation of the Julian date/time'''
    @staticmethod
    def get_modified_julian_date():
        t = astropy.time.Time(datetime.now())
        t.format = "mjd"
        return float(str(t))

    '''Auxiliary function for converting int to bytes'''
    @staticmethod
    def int_to_bytes(value):
        return struct.pack("B", value)

    '''Auxiliary function for converting resistance to temperature
    Params:
        resistance: The measured resistance (ohms)
        resistance_25C: The thermistor resistance at 25C (ohms)
        beta: The thermistor beta coefficient

    Returns: measured temperature in degrees C'''
    @staticmethod
    def resistance_to_temp(resistance, resistance_25C, beta):
        return 1 / (1 / (25 + Constants.KELVINS_TO_CELCIUS) + np.log(resistance / resistance_25C) / beta) - Constants.KELVINS_TO_CELCIUS

    '''Converts an entire array of resistances to temperature. Properly handles
    infinite resistances and unconfigured channels
        Params:
        resistances: The measured resistance (ohms)
        resistances_25C: The thermistor resistance at 25C (ohms)
        beta: The thermistor beta coefficient

    Returns: measured temperature in degrees C as an array'''
    @staticmethod
    def resistance_to_temp_array(resistances, resistances_25C, beta):
        temps = np.full(len(resistances), -np.inf) #Filled with minus infinities
        for i in range(len(resistances)):
            if resistances[i] != np.inf and resistances_25C[i] != np.inf and beta[i] != 0:
                temps[i] = Tools.resistance_to_temp(resistances[i], resistances_25C[i], beta[i])
        return temps

    '''Returns the time a file was last modified'''
    @staticmethod
    def when_last_modified(filename):
        return os.stat(filename)[8] #just trust me this works

    '''Converts channel number 101-120 and 201-220 into indices in the array
    of data returned. For Keithley'''
    @staticmethod
    def channel_number_to_array_index(channel_number):
        if 101 <= channel_number <= 120:
            return channel_number-101
        elif 201 <= channel_number <= 220:
            return channel_number-181
        else:
            raise ValueError("ERROR: Invalid channel number " + str(channel_number))

    '''Converts array index in data received from Keithley to its channel number.'''
    @staticmethod
    def array_index_to_channel_number(index):
        if 0 <= index < 20:
            return index + 101
        elif 20 <= index < 40:
            return index + 181
        else:
            raise ValueError("ERROR: Invalid array index " + str(index))


if __name__ == "__main__":
    master = Servo_Master("config_blues.txt")
    master.start()
