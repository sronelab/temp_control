import numpy as np
import socket
from Tools import Tools
import os
import json


DIRECTORY = os.getcwd() #We want to save our current directory!



'''Class corresponding to a particular Keithley DMM.'''
class Keithley_DMM():

    #This is extended and modified from the old keithley class in Keithley.py

    NUM_CHANNELS = 40

    '''Initializes the Keithley.
    Params:
        name: A unique name identifying the Keithley
        params: The dict of params used to initialize the Keithley, from parsing the config file

    Required params:
        "address" (ip address)

    Required channel params (when configuring channels):
        "resistance_25C": Resistance of thermistor at 25C
        "beta": Thermistor beta coefficient

    Optional channel params:
        "offset": A constant resistance offset due to cables, etc.
'''
    def __init__(self, name, params):
        self.port = 1394 #2701 port
        self.buffer_size=2048
        print(params)
        self.ip_address = params["address"]
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
    def configure_channel(self, channel_number, params):
        index = Tools.channel_number_to_array_index(channel_number)
        self.channel_names[index] = params["name"]
        self.resistance_25C[index] = params["resistance_25c"]
        self.beta[index] = params["beta"]
        self.offset[index] = params["offset"] if "offset" in params else 0

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
