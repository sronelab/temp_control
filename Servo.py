import numpy as np
import Constants


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
    def __init__(self, name, params, master, input_device, output_device):
        self.name = name
        self.params = params
        self.current_reading = -np.inf
        self.previous_reading = -np.inf
        self.integral_value = 0
        self.keithley = input_device
        self.output_device = output_device
        
        print('Params')
        print(params)

    '''Resets numerical parameters in the servo loop without clearing memory.

    Params:
        k_prop: Proportional gain coefficient
        t_int: Integration time
        t_diff: Differentiation time
        setpoint: The setpoint of the control variable
        timestep: How often to refresh the control loop (sec)'''
    def refresh_parameters(self, params):
        self.params = params
        print("Refreshed parameters for servo " + self.name)

    '''Clears the accumulated value on the integrator. The main reason you
    would want to call this is in case of severe integrator windup.'''
    def reset_integrator(self):
        self.integral_value = 0
        print("Reset integrator for servo " + self.name)

    '''Calculates and returns the error signal'''
    def error_signal(self):
        return self.params["setpoint"] - self.current_reading

    '''Calculates and returns the output signal'''
    def output_signal(self):
        error = self.error_signal()
        k = self.params["k"]
        prop = k * error
        integral = k * self.integral_value
        diff = k * (self.current_reading - self.previous_reading) * self.params["t_diff"]/Constants.Constants.BASE_TICK_INTERVAL
        return prop+integral+diff

    '''Performs one iteration of the servo loop.'''
    def update(self):
        self.previous_reading = self.current_reading
        self.current_reading = self.keithley.get_temp(self.params["input_channel"])
        print('Current reading (C) for ' + str(self.name) + ' ' + str(self.current_reading))
        if (self.previous_reading != -np.inf and self.current_reading != -np.inf): #Avoid error on startup
            self.integral_value += self.error_signal() * Constants.Constants.BASE_TICK_INTERVAL / self.params["t_int"]
            output_signal = self.output_signal()
            output = float(output_signal) + float(self.params.get("output_default", 0))
            control_var = min(max(output, self.params.get("output_min", -np.inf)), self.params.get("output_max", np.inf))
            if control_var != output:
                print("ERROR: tried to write control variable outside limits")
            self.output_device.write(control_var, channel = int(self.params.get("output_channel", 0)))

    '''Closes the servo by resetting output device to a default that might be provided'''
    def close(self):
        if "output_default" in self.params:
            self.output_device.write(self.params["output_default"], channel = self.params.get("output_channel", 0))
