'''Script for running temperature control servos.

@author Josie Meyer, josephine.meyer@colorado.edu'''

#Abominated (altered) by TB 07/2020
#Mostly changed to put classes in separate files for readability.
#Added Rigol voltage control for actuation of Sr1 Table Temps

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
from Chiller import Chiller
from Keithley_DMM import Keithley_DMM
from Tools import Tools
from Servo import Servo
from Aux_Timer import Aux_Timer
import sys
from rigol_dp832a import rigol_dp832a
import Constants

#flush buffer for disown script to get it write to file
sys.stdout.flush()

#Get better performance by optimizing range functions in Python 2, 3
try:
    range = xrange
except NameError:
    pass



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
        self.current_device = "" #ignore, for implementation only
        self.parse_config_file(config_filename)
        self.clock_flag = threading.Event()
        self.timer = Aux_Timer(Constants.Constants.BASE_TICK_INTERVAL,
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
                if len(tokens) == 1: #title
                    title = tokens[0]
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
        elif title == "channels":
            pass
        elif title in self.devices:
            self.configure_channel_from_tokens(tokens, title)
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
        name = tokens[0].strip(":")
        if name in self.devices: #Check if we already have the device
            return #We already have the device initialized
        #Either the device hasn't been initialized yet, or has changed

        try:
            _, params = self.pair_tokens(tokens)
        except ValueError:
            print("Error: unable to configure device " + tokens[0] + " due to incorrect number of tokens")
            return

        if "type" not in params:
            print("Error: device missing parameter 'type'")
            return

        if params["type"] == "rigol_dp832a":
            try:
                self.devices[name] = rigol_dp832a(name, params)
            except Exception as e:
                print("ERROR: Unable to initialize Rigol: " + name)
                raise(e)

        elif params["type"] == "chiller":
            try:
                self.devices[name] = Chiller(name, params)
            except Exception as e:
                print("ERROR: Unable to initialize chiller: " + name)
                raise(e)
        elif params["type"] == "keithley":
            try:
                self.devices[name] = Keithley_DMM(name, params)
            finally:
                pass #TODO
#            except Exception as e:
#                print("ERROR: Unable to initialize Keithley: " + name)
#                raise(e)
        else: #We have an unrecognized device type:
            raise ValueError("Unrecognized device type")

    '''Configures a channel from tokens extracted from the config file.
    Prints an error message but does not propagate exceptions.

    Params:
        tokens: Tokens from the config file'''
    def configure_channel_from_tokens(self, tokens, device_name):
        try:
            channel_number, params = self.pair_tokens(tokens)
        except ValueError:
            print("Error: unable to configure channel " + tokens[0] + " due to incorrect number of tokens")

        if not device_name in self.devices:
            raise ValueError("Unrecognized device name: " + device_name)

        self.devices[device_name].configure_channel(channel_number, params)

    '''Pairs tokens into dictionary. Returns the name/channel number before the colon, followed by a dict of parameters'''
    def pair_tokens(self, tokens):
        if len(tokens) // 2 == 0: #We should have an odd number of tokens!
            raise ValueError("Must be an odd number of tokens")
        params = {}
        num_params = len(tokens) // 2
        for i in range(num_params):
            parameter_name = tokens[1 + 2*i]
            parameter_value_string = tokens[2 + 2*i]
            try: #convert strings to literal number, see if it works
                parameter_value = float(parameter_value_string)
                if parameter_value == int(parameter_value):
                    parameter_value = int(parameter_value)
            except ValueError as e:
                parameter_value = parameter_value_string
            params[parameter_name] = parameter_value

        header_string = tokens[0].strip(":")
        try:
            header = float(header_string)
        except ValueError, TypeError:
            header = header_string
        return header, params


    '''Configures a servo loop from tokens extracted from the config file.
    Prints an error message but does not propagate exceptions if a servo loop
    cannot be constructed.

    Params:
        tokens: Tokens from the config file'''

    def configure_servo_from_tokens(self, tokens):
        try:
            servo_name, params = self.pair_tokens(tokens)
        except ValueError:
            print("ERROR: unable to configure servo " + servo_name + " due to even number of tokens")

        #Check if required parameters are present
        for required_parameter in ["input_device", "output_device", "setpoint", "k", "t_int", "t_diff"]:
            if required_parameter not in params:
                print("Error establishing servo with name " + servo_name + " because required parameter " + required_parameter + " missing")
                return

        #Check if devices are recognized and same as before (if relevant)
        if params["input_device"] not in self.devices:
            print("Error: unrecognized input device name: " + params["input_device"])
        elif params["output_device"] not in self.devices:
            print("Error: unrecognized output device name: " + params["output_device"])
        elif servo_name in self.servos and params["input_device"] == self.servos[servo_name].keithley and params["output_device"] == self.servos[servo_name].output_device:
            self.servos[servo_name].refresh_parameters(params)
        else:
            input_device = self.devices[params["input_device"]]
            output_device = self.devices[params["output_device"]]
            self.servos[servo_name] = Servo(servo_name, params, self, input_device, output_device)


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
        try:
            logging_freq = Constants.Constants.LOGGING_INTERVAL // Constants.Constants.BASE_TICK_INTERVAL
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
                    print("Config file changed")
                    self.refresh()
                    print("Loop parameters updated successfully.")
                for device in self.devices.values():
                    if isinstance(device, Keithley_DMM):
                        device.read()
        finally: #called to clean up devices and servos
            '''for servo in self.servos.values():
                servo.close()
            for device in self.devices.values():
                device.close()''' #TODO fix


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
            line = line.strip().lower().replace("=", " ").replace(":", " ").replace(",", " ")
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
            current_token = ""
            current_list = []
            for token in raw_tokens: #this is all quote mark, equals, and bracket handling!
                if in_quote:
                    if token[-1] == '"':
                        in_quote = False
                        tokens.append(current_token + " " + token[:-1])
                        current_token = ""
                    else:
                        current_token += (" " + token)
                else:
                    if token[0] == '"':
                        if token[-1] == '"':
                            tokens.append(token[1:-1])
                        else:
                            in_quote = True
                            current_token = token[1:]
                    else:
                        tokens.append(token)
            return tokens



if __name__ == "__main__":
    master = Servo_Master("config_blues.txt")
    master.start()
