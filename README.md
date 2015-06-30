# LabJackTemperatureLogger
A temperature logger using the LabJack U6.

# Prerequisites
Requires a LabJack driver and LabJackPython.

## To run on the Raspberry Pi
* install libusb-1.0 and libusb-1.0-dev
* build and install the LabJack exodriver (https://github.com/labjack/exodriver.git)
* install LabJacKPython (https://github.com/labjack/LabJackPython.git)

May work as a cron job, but probably needs to be on the python path.
Alternatively:
* ssh in
* > nohup python ljTempLogger.py &
* > logout
