import BaseHTTPServer
import SocketServer
import threading
import time
import u6
from ktypeExample import mVoltsToTempC, tempCToMVolts

# AIN1 screw terminal is physically closest to internal T-sensor.
CHANNEL = 1
# Cold junction offset measured with thermapen: T_measured - T_internal.
CJOFFSET = 1.4
# Kelvin to DegC offset.
KCOFFSET = 273.15
# Web port
PORT = 8000


class HTTPRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_HEAD(s):
        s.send_response(200)
        s.send_header("Content-type", "text/html")
        s.end_headers()


    def do_GET(s):
        """Respond to a GET request."""
        s.send_response(200)
        s.send_header("Content-type", "text/html")
        s.end_headers()
        s.wfile.write("<html><head><title>Title goes here.</title></head>")
        s.wfile.write("<body><p>This is a test.</p>")
        # If someone went to "http://something.somewhere.net/foo/bar/",
        # then s.path equals "/foo/bar/".
        s.wfile.write("<p>You accessed path: %s</p>" % s.path)
        s.wfile.write("</body></html>")


class TemperatureLogger(object):
    def __init__(self):
        # The U6 device.
        self.d = u6.U6()
        # Logged values
        self.log = []
        # Interval
        self.dt = 1.
        # Worker thread
        self.worker = threading.Thread(target=self.run)
        self.worker.daemon = True
        # Run flag
        self.run_flag = True

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
        self.log = []
        tLast = 0
        while self.run_flag:
            tNow = time.time()
            if tNow >= tLast + self.dt:
                temperature = self.readTemperature()
                self.log.append((tNow, temperature))
                tLast = tNow
            time.sleep(0.1)


    def start(self):
        self.run_flag = True
        self.worker.start()


    def stop(self):
        self.run_flag = False
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
