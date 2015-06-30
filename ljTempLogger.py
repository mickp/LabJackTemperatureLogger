import BaseHTTPServer
import io
import re
import SocketServer
import threading
import time
import u6
from ktypeExample import mVoltsToTempC, tempCToMVolts

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FormatStrFormatter


# AIN1 screw terminal is physically closest to internal T-sensor.
CHANNEL = 1
# Cold junction offset measured with thermapen: T_measured - T_internal.
CJOFFSET = 1.4
# Kelvin to DegC offset.
KCOFFSET = 273.15
# Web port
PORT = 8000
# Refresh rate
REFRESH = 5000
# Format for filenames.
FILENAMESTR = r"%Y%m%d-%H%M%S.txt"
# URL matching strings
URLSTRINGS = {'img': r"/img\?.*",
              'current': "/current.*",
              'data': "/data.*"}
# URL return types.
URLTYPES = {'img': "image/png",
            'current': "text/plain",
            'default': "text/html"}
# HTML template for web view.
HTML = """
<html>
  <head>
    <title>Temperature logger.</title>
    <script type="text/javascript">
        function update(){
            var current = document.getElementById("current");
            var xmlhttp;
            xmlhttp = new XMLHttpRequest();
            xmlhttp.onreadystatechange = function() {
                current.innerHTML = parseFloat(xmlhttp.responseText).toFixed(1);
                }
            xmlhttp.open("GET","current", true);
            xmlhttp.send();
            var plot=  document.getElementById("plot");
            plot.src = plot.src.replace(/\?.*/,function () {
                return '?' + new Date();} )
        }
        window.setInterval(function() {update()}, %(REFRESH)d)
    </script>
  </head>
  <body>
    <h1>Temperature logger.</h1>
    <h2>Current temperature: <span id="current">%(CURRENT).1f</span>&deg;C </h2>
    %(TABLE)s
    <img id="plot" src="/img?" />
  </body>
</html>
"""

class LoggedData(object):
    rows = []
    outFile = None

    @staticmethod
    def getData():
        return LoggedData.outFile.name


    @staticmethod
    def getPlot():
        """Get the data as a plot."""
        # Convert timestamps to datetimes.
        epochs, temps = zip(*LoggedData.rows)
        times = mdates.num2date(mdates.epoch2num(epochs))

        # Create the plot.
        fig, ax = plt.subplots()
        ax.plot(times, temps)
        ax.xaxis.set_minor_locator(mdates.MinuteLocator())
        ax.xaxis.set_minor_formatter(mdates.DateFormatter('%H:%M:%S'))
        ax.xaxis.set_major_locator(mdates.HourLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M:%S'))
        ax.yaxis.set_major_formatter(FormatStrFormatter("%.1f"))
        # Format minor ticks.
        majlocs = ax.xaxis.get_majorticklocs()
        for loc, label in zip(ax.xaxis.get_minorticklocs(),
                                    ax.xaxis.get_minorticklabels()):
            # Rotate minor ticks
            label.set_rotation(90)
            # Hide minor ticks and major tick locations.
            if loc in majlocs:
                label.set_visible(False)
        # Rotate major ticks.
        for label in ax.xaxis.get_majorticklabels():
            label.set_rotation(90)
        # Make room for the tick labels.
        plt.subplots_adjust(bottom=.3)

        # Write the plot to a buffer as an image.
        buff = io.BytesIO()
        fig.canvas.print_figure(buff, format='png')
        # Must explicitly close the plot.
        plt.close()
        # Return the buffer contents.
        return buff.getvalue()

    @staticmethod
    def getCurrent():
        """Return the last measured temperature."""
        return LoggedData.rows[-1][1]


class HTTPRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_HEAD(s):
        """Send response header."""
        if None != re.search(URLSTRINGS['img'], s.path):
            s.send_response(200)
            s.send_header("Content-type", URLTYPES['img'])
        elif None != re.search(URLSTRINGS['current'], s.path):
            s.send_response(200)
            s.send_header("Content-type", URLTYPES['current'])
        #elif None != re.search(URLSTRINGS['data'], s.path):
        #    s.send_response(302)
        #    s.send_header("location", LoggedData.getData())
        else:
            s.send_response(200)
            s.send_header("Content-type", URLTYPES['default'])
        s.end_headers()


    def do_GET(s):
        """Respond to a GET request."""
        HTTPRequestHandler.do_HEAD(s)
        if None != re.search(URLSTRINGS['img'], s.path):
            # Serve the plot image
            s.wfile.write(LoggedData.getPlot())
        elif None != re.search(URLSTRINGS['current'], s.path):
            # Serve the current temperature.
            s.wfile.write(LoggedData.getCurrent())
        #elif None != re.search(URLSTRINGS['data'], s.path):
        #    pass
        #    #s.wfile.write(LoggedData.getData())
        else:
            # Serve the main page.
            body = HTML % {
                "CURRENT": LoggedData.getCurrent(),
                "REFRESH": REFRESH,
                "TABLE": ''}
            s.wfile.write(body)


class TemperatureLogger(object):
    def __init__(self):
        # The U6 device.
        self.d = u6.U6()
        # Interval
        self.dt = 1.
        # Worker thread
        self.worker = threading.Thread(target=self.run)
        self.worker.daemon = True
        # Run flag
        self.runFlag = True

        # Fetch calibration data and configure d.
        self.d.getCalibrationData()


    def readTemperature(self):
        d = self.d
        # Cold junction in degC, with sensor-terminal offset compensation.
        coldJunc_C = d.getTemperature() + CJOFFSET - KCOFFSET
        # Cold junction im mV (from inverse k-type polynomial).
        coldJunc_mV = tempCToMVolts(coldJunc_C)
        # Remote junction mV.
        couple_mV = d.getAIN(CHANNEL, resolutionIndex=8, gainIndex=3) * 1000.
        # Cold junction + remote junction mV.
        total_mV = coldJunc_mV + couple_mV
        # Return 0-referenced temperature (from k-type polynomial).
        return mVoltsToTempC(total_mV)


    def run(self):
        # Initialised data store.
        LoggedData.rows = []
        # Time at last log entry.
        tLast = 0
        # Filename for log file.
        filename = time.strftime(FILENAMESTR, time.localtime())
        # The log file.
        LoggedData.outFile = open(filename, 'w')
        LoggedData.outFile.write("time\ttemperature\n")
        t0 = time.time()
        while self.runFlag:
            tNow = time.time()
            if tNow >= tLast + self.dt:
                temperature = self.readTemperature()
                LoggedData.rows.append((tNow, temperature))
                tLast = tNow
                outStr = "%f\t%.1f\n" % (tNow - t0, temperature)
                LoggedData.outFile.write(outStr)
                LoggedData.outFile.flush()
            time.sleep(0.1)
        LoggedData.outFile.close()


    def start(self):
        self.runFlag = True
        self.worker.start()


    def stop(self):
        self.runFlag = False
        self.worker.join()



def main():
    # Logger
    logger = TemperatureLogger()
    logger.start()
    # HTTP server
    httpd = SocketServer.TCPServer(("", PORT), HTTPRequestHandler)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    logger.stop()


if __name__ == '__main__':
    main()
