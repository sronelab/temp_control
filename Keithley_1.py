

#Modified by Josie from Keithley.py

import socket
import numpy as np

try: #Optimize range function for Python 2, 3
    range = xrange
except NameError:
    pass

class keithley():
#Initialization. 
    
    '''Initializes the Keithley.
    Params:
        IP_address: The IP address of the Keithley.'''
    def __init__(self,ip_address):
        #Temporary set ipAddress to useful thing
        self.port = 1394 #2701 port #we now have port 30
        self.buffer_size=1024
        self.ip_address = ip_address
    
    '''Reads resistances from the Keithley.
    Returns: A length-40 numpy array containing the resistances of all channels.'''    
    def read_resistances(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((self.ip_address, self.port))
            data_card_1 = self.read_data_from_card(sock, 101, 120)
            data_card_2 = self.read_data_from_card(sock, 201, 220) 
            #note: this fails even if I query the same card twice
            #note: this fails even if I use a different socket for each call to read_data_from_card
        finally:
            sock.close()
        return np.concatenate((data_card_1, data_card_2))
    
    '''Directly queries the card and extracts the resistances from the data.
    
    Params:
        sock: The socket to communicate with the card
        channel_min: The minimum channel number to query (101 or 201)
        channel_max: The maximum channel number to query (120 or 220)
        
    Returns: a length-20 numpy array containing the resistances of the channels'''
    def read_data_from_card(self, sock, channel_min, channel_max):
        sock.send("*RST \n") #Resets Keithley
        sock.send("FUNC 'RES',(@{cmin}:{cmax}) \n".format(cmin=str(channel_min), cmax=str(channel_max)))
        sock.send("RES:RANG:AUTO ON \n")
        
        sock.send("RES:NPLC 5,(@{cmin}:{cmax}) \n".format(cmin=str(channel_min), cmax=str(channel_max)))
        #5 is slow 1 is medium .1 is fast
        sock.send("TRAC:CLE \n") #Clear buffer
        sock.send("INIT:CONT OFF \n")
        sock.send("TRIG:SOUR IMM \n")
        sock.send("TRIG:COUN 1 \n")
        sock.send("SAMP:COUN 20\n")
        sock.send("ROUT:SCAN (@{cmin}:{cmax}) \n".format(cmin=str(channel_min), cmax=str(channel_max)))
        #Sets scan route 1 to 20 here
        
        sock.send("ROUT:SCAN:TSO IMM \n")
        sock.send("ROUT:SCAN:LSEL INT \n")
        sock.send("READ? \n")
        
        data = str(sock.recv(self.buffer_size)).split(',')
        print("data", data)
        resistances = []
        if not data:
            print("ERROR we didn't receive any data")
        for i in range(0, 20):
            resistance = float(data[i*3].strip('OHM'))
            if resistance == 9.9E37: #Constant returned for open circuit
                resistance = np.inf
            resistances.append(resistance)
        return np.array(resistances)