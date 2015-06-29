import u6
from ktypeExample import mVoltsToTempC, tempCToMVolts

CHANNEL = 0

def main():
    d = u6.U6()
    d.getCalibrationData()

    def readTemperature():
        coldJunc_C = d.getTemperature() + 2.5 - 273.15  
        coldJunc_mV = tempCToMVolts(coldJunc_C)
        couple_mV = d.getAIN(0, resolutionIndex=8, gainIndex=3) * 1000.
        total_mV = coldJunc_mV + couple_mV
        return mVoltsToTempC(total_mV)
    

    while True:
        print readTemperature()

if __name__ == main():
    main()