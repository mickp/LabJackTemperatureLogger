import datetime
import time
import sys
import u6
from ktypeExample import mVoltsToTempC, tempCToMVolts

# AIN1 screw terminal is physically closest to internal T-sensor.
CHANNEL = 1
# Cold junction offset measured with thermapen: T_measured - T_internal.
CJOFFSET = 1.4
# Kelvin to DegC offset.
KCOFFSET = 273.15


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


def main(period=1., target=None):
    # Data source
    source = DaqU6()
    # Data target
    target = target
    # Sampling period / s
    period = period

    while True:
        tic = time.time()
        timestamp = datetime.datetime.now().isoformat()
        temperature = source.readTemperature()
        output = "%s %f\n" % (timestamp, temperature)
        if target:
            with open(target, 'a') as f:
                f.write(output)
        else:
            sys.stdout.write(output)
        time.sleep(period - (time.time() - tic))

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Log temperature from thermocouple.')
    parser.add_argument('period', metavar='period', type=float, nargs='?',
                   help='sampling period in seconds')
    parser.add_argument('target', metavar='target', type=str, nargs='?', default=None,
                   help='(optional) output file')

    args = parser.parse_args()
    main(args.period, args.target)