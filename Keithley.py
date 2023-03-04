#Class for establishign functions to control our Keithley 2701 through Ethernet to USB. Currently reads all resistances...

import socket
import time, datetime
import os
import numpy as np

class keithley():
#Initialization. 

	def __init__(self,ip_address,num_channels = 20):
		#Temporary set ipAddress to useful thing
		self.port = 1394 #2701 port #we now have port 30
		self.buffer_size=1024
		self.ip_address = ip_address
		self.num_channels = 20
        
    def read_resistances_josie(self):
        data = []
        
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self.ip_address, self.port))
        
        s.send("*RST \n")



	#Returns the frequency of the channel of the selected rigol.

	def read_resistances(self):
		#Uninitialized data
		data = []

		#Open socket and ask for frequency
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		s.connect((self.ip_address, self.port))

		#Set up Keithley get the datas
		s.send("*RST \n") #Resets Keithley
		s.send("FUNC 'RES',(@101:120) \n")
		s.send("RES:RANG:AUTO ON \n")

		#s.send("DISPlay:ENABle ON \n")
		s.send("RES:NPLC 5,(@101:120) \n") #5 is slow 1 is medium .1 is fast
		s.send("TRAC:CLE \n") #Clear buffer
		s.send("INIT:CONT OFF \n")
		s.send("TRIG:SOUR IMM \n")
		s.send("TRIG:COUN 1 \n")
		s.send("SAMP:COUN 20\n")
		s.send("ROUT:SCAN (@101:120) \n") #Sets scan route 1 to 20 here
		s.send("ROUT:SCAN:TSO IMM \n")
		s.send("ROUT:SCAN:LSEL INT \n")
		s.send("READ? \n")

		#time.sleep(.1)
		data = str(s.recv(self.buffer_size))
		data = data.split(',')

		#Keithley returns a lot of other stuff currently, this ignores the returns we dont use and processes the ones we do
		resistances = []
		for i in range(0,20): #Dhruv data processing match to SAMP:COUN
			resistances.append(data[i*3])
			resistances[i] = float(resistances[i].strip('+OHM').strip('OHM'))
			if resistances[i] == 9.9E37:
			     resistances[i] = np.inf
			print(resistances[i])					

		s.close()
		return np.array(resistances)

	def read_resistances_slot_2(self):
		#Uninitialized data
		data = []

		#Open socket and ask for frequency
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		s.connect((self.ip_address, self.port))

		#Set up Keithley get the datas
		s.send("*RST \n") #Resets Keithley
		s.send("FUNC 'RES',(@201:220) \n")
		s.send("RES:RANG:AUTO ON \n")

		#s.send("DISPlay:ENABle ON \n")
		s.send("RES:NPLC 5,(@201:220) \n") #5 is slow 1 is medium .1 is fast
		s.send("TRAC:CLE \n") #Clear buffer
		s.send("INIT:CONT OFF \n")
		s.send("TRIG:SOUR IMM \n")
		s.send("TRIG:COUN 1 \n")
		s.send("SAMP:COUN 20\n")
		s.send("ROUT:SCAN (@201:220) \n") #Sets scan route 1 to 20 here
		s.send("ROUT:SCAN:TSO IMM \n")
		s.send("ROUT:SCAN:LSEL INT \n")
		s.send("READ? \n")

		#time.sleep(.1)
		data = str(s.recv(self.buffer_size)) #TODO figure out why receiving empty string
		data = data.split(',')

                
		#Keithley returns a lot of other stuff currently, this ignores the returns we dont use and processes the ones we do
		resistances = []
		for i in range(0,20):
			resistances.append(data[i*3])
			resistances[i] = float(resistances[i].strip('+OHM').strip('OHM'))
			if resistances[i] == 9.9E37:
			     resistances[i] = np.inf
			print(i, resistances[i])
		

		s.close()
		return np.array(resistances)



	def read_voltages(self):

		#Uninitialized data
		data = []

		#Open socket and ask for frequency
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		s.connect((self.ip_address, self.port))

		#Set up Keithley get the datas
		s.send("*RST \n") #Resets Keithley
		s.send("FUNC 'VOLT:DC',(@101:120) \n")
		s.send("RES:RANG:AUTO ON \n")
		#s.send("DISPlay:ENABle ON \n")
		s.send("RES:NPLC 5,(@101:120) \n") #5 is slow 1 is medium .1 is fast
		s.send("TRAC:CLE \n") #Clear buffer
		s.send("INIT:CONT OFF \n")
		s.send("TRIG:SOUR IMM \n")
		s.send("TRIG:COUN 1 \n")
		s.send("SAMP:COUN 20\n")
		s.send("ROUT:SCAN (@101:120) \n") #Sets scan route 1 to 20 here
		s.send("ROUT:SCAN:TSO IMM \n")
		s.send("ROUT:SCAN:LSEL INT \n")
		s.send("READ? \n")

		#time.sleep(.1)
		data = str(s.recv(self.buffer_size))
		data = data.split(',')

		#Keithley returns a lot of other stuff currently, this ignores the returns we dont use and processes the ones we do
		voltages= []
		for i in range(0,20):
			voltages.append(data[i*3])
			voltages[i] = float(voltages[i].strip('VDC'))

		s.close()
		return np.array(voltages)


