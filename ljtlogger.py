import BaseHTTPServer
import daqlog
import SocketServer
import re
import u6
from ktypeExample import mVoltsToTempC, tempCToMVolts

# Logging rate / ms
LOGRATE = 1000
# Web refresh rate / ms
REFRESH = 5000
# AIN1 screw terminal is physically closest to internal T-sensor.
CHANNEL = 1
# Cold junction offset measured with thermapen: T_measured - T_internal.
CJOFFSET = 1.4
# Kelvin to DegC offset.
KCOFFSET = 273.15
# Web port
PORT = 8000
# URL matching strings
URLSTRINGS = {'long': r"/long\?.*",
              'short': r"/short\?.*",
              'current': "/current.*",
              'data': "/data.*"}
# URL return types.
URLTYPES = {'long': "image/png",
            'short': "image/png",
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
            var longHistory =  document.getElementById("longHistory");
            longHistory.src = longHistory.src.replace(/\?.*/,function () {
                return '?' + new Date();} )
            var shortHistory =  document.getElementById("shortHistory");
            shortHistory.src = shortHistory.src.replace(/\?.*/,function () {
                return '?' + new Date();} )
        }
        window.setInterval(function() {update()}, %(REFRESH)d)
    </script>
  </head>
  <body>
    <h1>Temperature logger.</h1>
    <h2>Current temperature: <span id="current">%(CURRENT).1f</span>&deg;C </h2>
    %(TABLE)s
    <img id="longHistory" src="/long?" width=45%% float=left />
    <img id="shortHistory" src="/short?" width=45%% float=left />
  </body>
</html>
"""


class HTTPRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_HEAD(self):
        """Send response header."""
        if None != re.search(URLSTRINGS['long'], self.path):
            self.send_response(200)
            self.send_header("Content-type", URLTYPES['long'])
        if None != re.search(URLSTRINGS['short'], self.path):
            self.send_response(200)
            self.send_header("Content-type", URLTYPES['short'])
        elif None != re.search(URLSTRINGS['current'], self.path):
            self.send_response(200)
            self.send_header("Content-type", URLTYPES['current'])
        else:
            self.send_response(200)
            self.send_header("Content-type", URLTYPES['default'])
        self.end_headers()


    def do_GET(self):
        """Respond to a GET request."""
        HTTPRequestHandler.do_HEAD(self)
        if None != re.search(URLSTRINGS['long'], self.path):
            # Serve the plot image
            self.wfile.write(self.__class__.getLongHistory())
        if None != re.search(URLSTRINGS['short'], self.path):
            # Serve the plot image
            self.wfile.write(self.__class__.getShortHistory())
        elif None != re.search(URLSTRINGS['current'], self.path):
            # Serve the current temperature.
            self.wfile.write(self.__class__.getCurrent())
        else:
            # Serve the main page.
            body = HTML % {
                "CURRENT": self.__class__.getCurrent(),
                "REFRESH": REFRESH,
                "TABLE": ''}
            self.wfile.write(body)


class DaqU6(object):
    def __init__(self):
        self.d = None
        self.connect


    def connect(self):
        if self.d:
            try:
                self.d.close()
            except:
                pass
        del(self.d)
        self.d = u6.U6()
        self.d.getCalibrationData()


    def readTemperature(self):
        try:
            temperature = self._readTemperature()
        except:
            self.connect()
            temperature = self._readTemperature()
        return temperature
    

    def _readTemperature(self):
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


def test():
    # Logger
    logger = daqlog.DataHandler()
    logger.start()
    # Data source
    source = DaqU6()
    # Acquirer
    daq = daqlog.Acquirer(LOGRATE/1000., source.readTemperature, logger.addToQueue)
    daq.start()
    # Plotters
    plotterLong = daqlog.Plotter(REFRESH/1000., logger.getLongHistory)
    plotterLong.start()
    plotterShort = daqlog.Plotter(REFRESH/1000, logger.getShortHistory)
    plotterShort.start()

    return (daq, logger, plotterLong, plotterShort)


def main():
    # Logger
    logger = daqlog.DataHandler()
    logger.start()
    # Data source
    source = DaqU6()
    # Acquirer
    daq = daqlog.Acquirer(LOGRATE/1000., source.readTemperature, logger.addToQueue)
    daq.start()
    # Plotters
    plotterLong = daqlog.Plotter(REFRESH/1000., logger.getLongHistory)
    plotterLong.start()
    plotterShort = daqlog.Plotter(REFRESH/1000, logger.getShortHistory)
    plotterShort.start()

    # HTTP server
    class MyRequestHandler(HTTPRequestHandler):
        @staticmethod
        def getCurrent():
            return daq.last

        getLongHistory = plotterLong.getPlot
        getShortHistory = plotterShort.getPlot

        # Dummy log_message.
        def log_message(self, *args, **kwargs):
            return


    httpd = SocketServer.TCPServer(("", PORT), MyRequestHandler)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    logger.stopAndJoin()
    daq.stopAndJoin()
    plotterLong.stopAndJoin()
    plotterShort.stopAndJoin()

if __name__ == '__main__':
    main()