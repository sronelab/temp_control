import astropy
from datetime import datetime
import os
import numpy as np



DIRECTORY = os.getcwd() #We want to save our current directory!


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
        return 1 / (1 / (25 + 273.15) + np.log(resistance / resistance_25C) / beta) - 273.15

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
            return int(channel_number-101)
        elif 201 <= channel_number <= 220:
            return int(channel_number-181)
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
