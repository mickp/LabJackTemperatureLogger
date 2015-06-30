import u6
from ktypeExample import mVoltsToTempC, tempCToMVolts

# AIN1 screw terminal is physically closest to internal T-sensor.
CHANNEL = 1
# Cold junction offset measured with thermapen: T_measured - T_internal.
CJOFFSET = 1.4
# Kelvin to DegC offset.
KCOFFSET = 273.15

def main():
    # The U6 device.
    d = u6.U6()
    # Fetch calibration data and configure d.
    d.getCalibrationData()

    def readTemperature():
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
    

    while True:
        print readTemperature()

if __name__ == '__main__':
    main()