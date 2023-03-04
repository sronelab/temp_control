import threading
import time

'''Auxiliary timer class that controls timing via an external thread.'''
class Aux_Timer(threading.Thread):

    '''Initialized the timer thread. Tells the main thread when to update the
    servo loops and when to refresh the servo loop parameters.
    Params:
       Tick_interval: How often the clock should tick.
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
