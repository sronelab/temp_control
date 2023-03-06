import base64
from io import BytesIO
from flask import Flask, render_template_string
from matplotlib.figure import Figure
import numpy as np
import datetime
import json
import os

# Data part
## Formating date
datetime_fmt = '%Y.%m.%d'
def date_to_mjd(date_string):
    # convert from 'YYYY.MM.DD' date to MJD
    
    dt = datetime.datetime.strptime(date_string, datetime_fmt)
    
    JD = dt.toordinal() + 1721424.5 # convert to julian date (JD)
    MJD = JD - 2400000.5 # convert to modified JD (MJD)
    
    today = int(MJD) # rounding to the integer day
    
    return str(today)


# Flask app
app = Flask(__name__)

@app.route("/")
def index():
    return render_template_string('''
        <html>
            <head>
                <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
                <script>
                    $(document).ready(function() {
                        setInterval(function() {
                            var width = $(window).width();
                            var height = $(window).height();
                            $.ajax({
                                url: "/plot?width=" + width + "&height=" + height,
                                success: function(data) {
                                    $('#plot').attr('src', 'data:image/png;base64,' + data);
                                }
                            });
                        }, 5000);
                    });
                </script>
            </head>
            <body>
                <img id="plot" src="" />
            </body>
        </html>
    ''')

@app.route("/plot")
def plot():

        # get the data path. 
    today = date_to_mjd(datetime.datetime.today().strftime(datetime_fmt))
    file_path = os.path.dirname(__file__)   
    file_keithley_1 = os.path.join(file_path, "..", 'Logging/keithley1/'+today+'.txt')
    file_keithley_2 = os.path.join(file_path, "..", 'Logging/keithley2/'+today+'.txt')

    channel_names_1 = ["nc00", "nc01", "nc02", "nc03",
                    "nc04", "nc05", "nc06", "nc07",
                    "nc08", "nc09", "nc10", "nc11",
                    "nc12", "nc13", "nc14", "nc15",
                    "nc16", "probe fiber", "blue master", "injection fiber",
                    "nc20", "nc21", "nc22", "nc23",
                    "nc24", "nc25", "nc26", "nc27", 
                    "nc28", "nc29", "nc30", "nc31",
                    "nc32", "nc33", "nc34", "nc35",
                    "nc36", "nc37", "nc38", "nc39"]

    channel_names_2 = ["XMOT Probe Retro Window"
    ,"XMOT Probe Retro Window"
    ,"MOT Coil N"   
    ,"MOT Coil S"   
    ,"XMOT Retro Window"   
    ,"XMOT Retro Window"    
    ,"6 Way Cross E"  
    ,"6 Way Cross W"   
    ,"X MOT Probe Input Window"  
    ,"X MOT Probe Input Window" 
    ,"X MOT Input Window"   
    ,"X MOT Input Window"  
    ,"Cavity Top Window"   
    ,"Cavity Top Window"   
    ,"Oven Valve"   
    ,"Chamber HEPA - Servo"        
    ,"Laser HEPA - Servo"   
    ,"Lattice Fiber Top"   
    ,"PMT Andor"   
    ,"X MOT Retro Table"   
    ,"Repump Box"   
    ,"6 CF Window Front Left"    
    ,"6 CF Window Front Right"    
    ,"6 CF Window Back Left"    
    ,"6 CF Window Back Right"  
    ,"X Input Table"   
    ,"TOP PDH PD Table"  
    ,"Absorption Fiber Middle Table"  
    ,"No Probe XArm Input Table"
    ,"Ion Pump"   
    ,"Ion Pump Table"   
    ,"813 Master"    
    ,"Red Lasers"   
    ,"Laser Table Partition"
    ,'813 Transmission PD'
    ,'Empty'
    ,'Chamber Yoke'
    ,'Empty'
    ,'Empty'
    ,'Empty']
                    
    # function for loading data in from the temp file
    def load_temps(path, channels):
        
        # read data in, each entry is a JSON dict, so we read in a list of JSON dicts
        data_load = []
        for line in open(path, 'r'):
            data_load.append(json.loads(line))
        
        # Extract timestamps
        times = np.transpose([data_load[n][0] for n in range(len(data_load))])
        
        # Extract temperatures
        temp = np.transpose([data_load[n][1] for n in range(len(data_load))])
        temps = {channels[entry]: temp[entry] for entry in range(40)}
        
        return times, temps


    # color scheme
    # Blue box
    colors = {'Probe Fiber': 'slategrey', 'Blue Master': 'lightskyblue', 'Injection Fiber': 'steelblue'}
    # Table: Laser side
    colors.update({'Laser HEPA - Servo': 'red', '813 Master': 'darkred', 'Red Lasers': 'indianred',
            'Laser Table Partition': 'orangered'})
    # Table: Chamber side
    colors.update({'6 Way Cross E': 'tab:blue', '6 Way Cross W': 'tab:orange', 'Oven Valve': 'tab:green', 
                'Chamber HEPA - Servo': 'tab:red', 'Lattice Fiber Top': 'tab:purple', 'PMT Andor': 'tab:brown',
                'X MOT Retro Table': 'tab:pink', 'X MOT Input Window': 'tab:gray', 'X Input Table': 'tab:olive',
                'TOP PDH PD Table': 'tab:cyan', 'Absorption Fiber Middle Table': 'lightsteelblue',
                'No Probe XArm Input Table': 'springgreen',
                'Ion Pump': 'burlywood', 'Ion Pump Table': 'slateblue', '813 Transmission PD': 'yellowgreen'})
    # Table: viewports
    colors.update({'XMOT Probe Retro Window': 'lightsteelblue', 'XMOT Retro Window': 'salmon',
                'X MOT Probe Input Window': 'steelblue',
                'X MOT Input Window': 'firebrick',  'Cavity Top Window': 'lightgrey',
                '6 CF Window Front Left': 'darkseagreen',
                '6 CF Window Back Left': 'seagreen',  'Chamber Yoke': 'tab:purple'})


    #Load data and prep time window
    times_1, temps_1 = load_temps(file_keithley_1, channel_names_1)
    times_2, temps_2 = load_temps(file_keithley_2, channel_names_2)
    use_all_data = True
    # use_all_data = 'no'
    if use_all_data==True:
        time_window=len(times_2) # uses all the data
    else:
        time_window = 200 # change this parameter to look at different time windows relative to the most recent point 

    # Main plot
    # Generate the figure **without using pyplot**.
    fig = Figure(figsize=(18, 10))
    axes = fig.subplots(2, 3)
    # Blues
    axes[0, 0].clear()
    axes[0, 0].plot((times_1 - times_1[0])[-time_window:]*24., temps_1['probe fiber'][-time_window:], '.', label='Probe Fiber', color=colors['Probe Fiber'])
    axes[0, 0].plot((times_1 - times_1[0])[-time_window:]*24., temps_1['blue master'][-time_window:], '.', label='Blue Master', color=colors['Blue Master'])
    axes[0, 0].plot((times_1 - times_1[0])[-time_window:]*24., temps_1['injection fiber'][-time_window:], '.', label='Injection Fiber', color=colors['Injection Fiber'])
    axes[0, 0].set(ylabel='Temperature (C)', xlabel='Time (Hours)', title="Blue table")
    axes[0, 0].grid()
    axes[0, 0].legend()


    # Red and lattice laser table 
    axes[0, 1].clear()
    thermistors = [16,31,32,33]
    for i in thermistors:
        axes[0, 1].plot((times_2 - times_2[0])[-time_window:]*24., temps_2[channel_names_2[i]][-time_window:],
                '.', label=channel_names_2[i], color=colors[channel_names_2[i]])
    axes[0, 1].set(ylabel='Temperature (C)', xlabel='Time (Hours)', title='689 and 813 table')
    axes[0, 1].legend()
    axes[0, 1].grid()

    # Main chamber
    thermistors = [6,7,14,15,17,18,19,10,25,26,27,28,29,30,34]#15#,31,32,33]
    axes[0, 2].clear()
    for i in thermistors:
        axes[0, 2].plot((times_2 - times_2[0])[-time_window:]*24., temps_2[channel_names_2[i]][-time_window:], '.', label=channel_names_2[i], color=colors[channel_names_2[i]])
    axes[0, 2].set(ylabel='Temperature (C)', xlabel='Time (Hours)', title='Main chamber')
    axes[0, 2].legend(fontsize="small", ncol=3)
    axes[0, 2].grid()

    #  View ports 
    axes[1, 0].clear()
    thermistors = [0,5,8,10,12,21,23,36]
    for i in thermistors:
        axes[1, 0].plot((times_2 - times_2[0])[-time_window:]*24., temps_2[channel_names_2[i]][-time_window:], '.', label=channel_names_2[i], color=colors[channel_names_2[i]])
    axes[1, 0].set(ylabel='Temperature (C)', xlabel='Time (Hours)', title='Chamber viewports')
    axes[1, 0].grid()
    axes[1, 0].legend()

    # MOT coils
    axes[1, 1].clear()
    thermistors = [2,3]
    for i in thermistors:
        axes[1, 1].plot((times_2 - times_2[0])[-time_window:]*24., temps_2[channel_names_2[i]][-time_window:], '.', label=channel_names_2[i])
    axes[1, 1].set(ylabel='Temperature (C)', xlabel='Time (Hours)', title='MOT coils')
    axes[1, 1].grid()
    axes[1, 1].legend()

    # Notes 
    axes[-1, -1].clear()
    axes[-1, -1].annotate(
        "Today: "+str(datetime.datetime.today().strftime(datetime_fmt))+
        "\n last update: {}".format(str(datetime.datetime.now())) +
        "\n - x-axis starts from 0:00 a.m."+
        "\n - For the close-up, go J/notebooks/[date]/plot_temps.ipynb",
        (0, 0.5))
    axes[-1, -1].axis("off")

    fig.suptitle("Sr1 live temperature monitor")
    # fig.tight_layout()

    # Save it to a temporary buffer.
    buf = BytesIO()
    fig.savefig(buf, format="png")
    # Embed the result in the html output.
    data = base64.b64encode(buf.getbuffer()).decode("ascii")
    return data

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8000)
