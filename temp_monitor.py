# -*- coding: utf-8 -*-
"""
Created on Thu Feb 06 15:07:30 2020

@author: Josie Meyer (josephine.meyer@colorado.edu)
"""

import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
import sys
import random
from temp_control import LineTokenizer, Tools, Constants #sister program
import threading
import time
import os
import signal

#GUI imports for PyQt5. Use pip install python-qt5 to get unofficial PyQt5 for Python 2.7
from PyQt5.QtWidgets import QApplication, QMainWindow, QMenu, QVBoxLayout, QSizePolicy, QMessageBox, QWidget, QPushButton
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

try:
    range = xrange
except NameError:
    pass

WAIT_NO_NEW_DATA = 5 #seconds
WAIT_CONFIG_FILE_CHANGED = .1 #seconds

LINE_COLORS = ["r-", "b-", "g-", "c-", "m-"]

class Config_File_Manager:

    '''Constructor'''
    def __init__(self, config_file):
        self.config_file = config_file
        self.current_keithley = "" #internal variable
        self.devices = {} #name->device_type
        self.keithleys = {} #nested dict: name->channel number->channel name
        self.file_last_modified = Tools.when_last_modified(config_file)

    '''Refreshes the file manager'''
    def refresh(self):
        return self.parse_config_file

    '''Parses the config file to identify instrument names and Keithley channels.
        Params:
            config_file: The config file
        Returns:
            0) A dictionary of device name: device type (both as str)
            1) A nested dictionary of Keithley name: channel number: channel name'''
    def parse_config_file(self):
        title = ""
        with open(config_filename) as f:
            for line in f:
                tokens = LineTokenizer.tokenize_line(line)
                if len(tokens) == 1 and tokens[0][-1] == ":": #title
                    title = tokens[0][:-1]
                else:
                    if title and tokens:
                        self.interpret_tokens(tokens, title)
        return parser.devices, parser.keithleys

    '''Interprets tokens from the config file.

    Params:
        tokens: Tokens from calling tokenize_line() on a line of config file
        title: The title/heading of the tokenized line within the config file'''
    def interpret_tokens(self, tokens, title):
        if not title:
            raise ValueError("ERROR: No title")
        elif title == "devices":
            self.add_device_from_tokens(tokens)
        elif title == "keithleychannels":
            if len(tokens) == 1: #We have the name of a Keithley
                self.current_keithley = tokens[0]
            elif not self.current_keithley in self.devices:
                raise ValueError("ERROR: Invalid Keithley name: " + self.current_keithley)
                #We don't have a valid Keithley name, or might have empty string if not initialized at all
            else:
                self.add_channel_from_tokens(tokens, self.current_keithley)
        elif title == "servos":
            pass #used only in temp_control.py
        else:
            raise ValueError("ERROR: Invalid title in config file: " + title)

    '''Adds a device based on tokens from the config file. Raises ValueError
    if incorrectly formatted tokens argument.

    Params:
        tokens: The tokens from the config file line representing the device'''
    def add_device_from_tokens(self, tokens):
        if len(tokens) != 3: #Too many or too few arguments for a device
            raise ValueError("ERROR: Invalid device info in config file")
        device_type = tokens[1]
        self.devices[tokens[0]] = device_type #device_type
        if device_type == "keithley":
            self.keithleys[tokens[0]] = {}

    '''Adds a channel based on tokens from the config file.'''
    def add_channel_from_tokens(self, tokens, device_name):
        if not device_name in self.keithleys:
            raise ValueError("Unrecognized device name")
        try:
            channel_number = int(tokens[0])
        except ValueError:
            raise ValueError("Invalid channel number")
        self.keithleys[device_name][channel_number] = tokens[1] #device name

    #TODO refactor a bunch of code

    '''Returns whether the config file has changed since last refresh.'''
    def config_file_has_changed(self):
        modification_time = Tools.when_last_modified(self.config_filename)
        if modification_time != self.file_last_modified:
            self.file_last_modified = modification_time
            print("Change detected in config file -- recalibrating")
            return True
        return False

'''Class that manages the data from one device that has logging enabled'''
class Device_Manager():

    '''Constructor.

    Params:
        device_name: The name of the device
        device_type: The type of the device, as a string. Currently "keithley",
            "rigol", and "chiller" are supported'''
    def __init__(self, device_name, device_type):
        self.device_name = device_folder
        self.device_type = device_type
        self.times = []
        self.data = []
        #set list length for expected data
        if device_type == "keithley" or device_type == "rigol":
            self.num_args = 2 #time, data
        elif device_type == "chiller":
            self.num_args = 3 #time, setpoint, actual_temp
        else:
            raise ValueError("Unrecognized device type")

    '''Reads data from file.

    Params:
        num_days: The number of days of data to attempt to return. May fail
            to acquire all because record is incomplete.
        start_date: The date to start looking for data. If None,
            assumes today is the last day

    Returns:
        0) A list of dates/times (as modified julian date)
        1) A (probably) multidimensional list of data for the device'''
    def read_data(self, num_days = 1, start_date = None):
        times_list = []
        temps_list = []
        if start_date is None:
            start_date = int(Tools.get_modified_julian_date()) + 1 - num_days
        for i in range(num_days):
            date = start_date + i
            times, data = read_data_from_date(i)
            times_list.append(times)
            data_list.append(data)
        self.times = times_list
        self.data = data_list
        return self.times, self.data


    '''Reads data from a single date.

    Params:
        date: The modified Julian date to read
    Returns: see read_data()'''
    def read_data_from_date(self, date):
        filename = os.path.join("Logging", self.device_name, str(date)+".txt")
        try:
            with open(filename, "r") as f:
                data = []
                dates_times = []
                for encoded_line in f:
                    line = json.loads(encoded_line) #loads a nested list
                    if len(line) != self.num_args:
                        raise ValueError("Incorrect number of arguments in line")
                    dates_times.append(line[0])
                    data.append(line[1:])
        except FileNotFoundError:
            return [], [] #returns nothing if file does not exist
        return dates_times, np.transpose(np.array(data)).tolist()

    #TODO implement data caching, deal with midnight

'''Main class for this file. Implements a PyQT5 GUI window for monitoring temps'''
class Temp_Monitor(QMainWindow):

    def __init__(self, config_file):
        QMainWindow.__init__(self)
        self.config_file_manager = Config_File_Manager(config_file)
        self.left = 10
        self.top = 10
        self.width = 1500
        self.height = 900
        self.title = "Ye Lab Temperature Monitor"
        self.devices, self.keithleys = self.config_file_manager.parse_config_file()
        self.init_UI()

    def init_UI(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)

        canvas = Plotter(self, width=4, height=2.5)
        canvas_2 = Plotter(self, width=4, height=2.5)
        canvas.move(0,0)
        canvas_2.move(460,0)
        canvas.set_data([[.1,.2,.3,.4,.5]],[[1,2,3,4,5]])
        canvas.set_title("Example title")

        canvas.show()
        canvas.set_data([[.1,.2,.3,.4,.5]],[[1,2,3,4,6]])
        canvas.refresh_plot()
        self.show()

    def refresh(self):
        #print("I'm refreshing") #TODO implement
        pass

'''Class implementing a canvas which plots temperatures on screen. Each plots
is an instance of this class'''
class Plotter(FigureCanvas):

    '''Constructor for the canvas.'''
    def __init__(self, parent=None, width=5, height = 4, dpi = 100):
        self.fig = Figure(figsize = (width, height), dpi = dpi)
        self.fig.add_subplot()
        self.fig.patch.set_facecolor("w")
        self.channel_names = {}
        self.times = [[]]
        self.data = [[]]
        FigureCanvas.__init__(self, self.fig)
        self.setParent(parent)
        FigureCanvas.setSizePolicy(self, QSizePolicy.Expanding, QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)
        self.set_up_plots()

    '''Sets the title of the plot'''
    def set_title(self, title):
        self.axes.set_title(title)

    '''Sets the data of the plot

    Params:
        times: A list of lists of times (as modified julian date) when data points were
            acquired. First index gives the channel, second the times
        data: A corresponding list of lists of temperatures (etc)'''
    def set_data(self, times, data):
        self.times = times
        self.data = data

    '''Clears the axes in the plot, to allow new data to be plotted'''
    def clear(self):
        for line in self.axes.lines:
            del line #we actually want to delete the object

    '''Plots the stored data on the axes'''
    def plot_stored_data(self):
        for i, (channel_times, channel_data) in enumerate(zip(self.times, self.data)):
            self.axes.plot(channel_times, channel_data, LINE_COLORS[i % len(LINE_COLORS)])

    '''Refreshes the plot and graphics. Call when you have new data'''
    def refresh_plot(self):
        self.clear() #clear the old lines
        self.plot_stored_data() #plot the new lines
        self.draw() #refresh the graphics

    '''Plots the data on the canvas'''
    def set_up_plots(self):
        self.axes = self.fig.add_subplot(111)
        self.axes.set_facecolor("w")
        self.refresh_plot()

class Temp_Monitor_Timer(QTimer):

    def __init__(self, temp_monitor):
        QTimer.__init__(self) #call the super constructor
        self.temp_monitor = temp_monitor
        self.timeout.connect(lambda: self.temp_monitor.refresh())
        self.start(100) #100 ms timer

'''Sets a variety of global parameters in matplotlib'''
def set_rc_params():
    mpl.rcParams['text.color'] = 'k'
    mpl.rcParams['axes.labelcolor'] = 'k'
    mpl.rcParams['xtick.color'] = 'k'
    mpl.rcParams['ytick.color'] = 'k'
    mpl.rc("axes", edgecolor = "k")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    set_rc_params()
    monitor = Temp_Monitor()
    timer = Temp_Monitor_Timer(monitor)
    sys.exit(app.exec_())
