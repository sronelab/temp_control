'''Class containing various exportable constants'''
class Constants:

    def __init__(self):
        pass

    #Constants
    BASE_TICK_INTERVAL = 30  #how often clock ticks to update servos (sec)
    LOGGING_INTERVAL = 30  #How often to log (sec)
    MAX_TRIALS_CHILLER = 5 #How many tries to communicate with chiller before giving up
    DEFAULT_CHILLER_SETPOINT = 21
    CHILLER_MAX = 50 #Maximum allowed setpoint, default
    CHILLER_MIN = 10 #Minimum allowed setpoint, default

    #Sr1 HEPA Valve Constants
    VALVE_V_MIN = 1.0
    VALVE_V_MAX = 5.0
    VALVE_V_DEFAULT = 3.0
