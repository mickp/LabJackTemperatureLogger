from collections import deque, Container
import io
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FormatStrFormatter
import threading
import time


class StartStopThread(threading.Thread):
    def __init__(self):
        super(StartStopThread, self).__init__()
        self.runFlag = None


    def start(self):
        self.runFlag = True
        super(StartStopThread, self).start()


    def stopAndJoin(self):
        self.runFlag = False
        self.join()


class Plotter(StartStopThread):
    def __init__(self, period, source):
        super(Plotter, self).__init__()
        self.period = period
        self.source = source
        self.plot = None
        self.lock = threading.Lock()

    
    def getPlot(self):
        with self.lock:
            if self.plot:  
                return self.plot.getvalue()
            else: 
                return None


    def run(self):
        tLast = 0
        while self.runFlag:
            time.sleep(self.period)
            tNow = time.time()
            if tNow >= tLast + self.period:
                data = self.source()
                # Convert timestamps to datetimes.
                times = mdates.num2date(mdates.epoch2num(list(data[0])))
                # Convert data to lists - deques do not support slicing.
                series = [list(d) for d in data[1:]]

                # Create the plot.
                fig, ax = plt.subplots(dpi=200)
                for s in series:
                    pts = min(len(times), len(s))
                    ax.plot(times[0:pts], s[0:pts])
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

                with self.lock:
                    if not self.plot:
                        self.plot = io.BytesIO()
                    self.plot.seek(0)
                    fig.canvas.print_figure(self.plot, format='png')
                    self.plot.flush()
                # Must explicitly close the plot.
                plt.close()
                tLast = tNow


class DataHandler(StartStopThread):
    def __init__(self, headings=None, cols=2, filenameStr='%Y%m%d-%H%M%S.txt', history=256):
        super(DataHandler, self).__init__()
        # Run flag.
        # self.runFlag = None
        # Settings for output file.
        self.fileSettings = {'headings':headings,
                          'filenameStr': filenameStr,}
        # Number of columns.
        self.nCols = cols
        # View data.
        self.longHistory = None
        self.shortHistory = None
        # Maximum points in view.
        self.historyLength = history
        # Queue for incoming data.
        self.queue = deque()
        # Lock on queue.
        self.lock = threading.Lock()
        

    def addToQueue(self, *data):
        """Add a point to the queue."""
        with self.lock:
            self.queue.append(data)


    def getLongHistory(self):
        with self.lock:
            return self.longHistory


    def getShortHistory(self):
        with self.lock:
            return self.shortHistory


    def run(self):
        """DataHandler main loop."""
        # Clear stale data from the queue.
        self.queue.clear()
        # Create the log file.#
        fileNameStr = self.fileSettings.get('filenameStr')
        fileName = time.strftime(fileNameStr, time.localtime())
        with open(fileName, 'w') as fh:
            headings = self.fileSettings.get('headings')
            if headings:
                fstr = '%s \t' * len(headings)
                print fstr, tuple(headings)
                fh.write(fstr % tuple(headings))
                fh.write('\n')
        # Denominator - for averaging.
        denom = 1
        # Count of data points in current view point.
        count = 0
        # Number of columns.
        nCols = self.nCols
        # Data format string.
        formatStr = self.fileSettings.get('formatStr')
        if not formatStr:
            formatStr = '%f\t' * nCols + '\n'
        elif not formatStr.endswith('\n'):
            formatStr += '\n'
        # view data
        self.longHistory = [ [] for col in range(nCols)]
        self.shortHistory = [ deque(maxlen=self.historyLength) for col in range(nCols)]
        
        while self.runFlag:
            if len(self.queue) == 0:
                # No data to process. Wait then skip to next iteration.
                time.sleep(1)
                continue
        
            # There is data to process.
            # Fetch oldest point in queue.
            with self.lock:
                newData = self.queue.popleft()
            # Throw away extra columns.
            if len(newData) > nCols:
                newData = newData[0:nCols]
            # Log data to file.
            with open(fileName, 'a') as fh:
                fh.write(formatStr % newData)
        
            # Add point to histories.
            # Short history.
            for i, value in enumerate(newData):
                self.shortHistory[i].append(value)

            # Long history.
            if count not in [0, denom]:
                # New data should be averaged into last view point.
                for i in range(nCols):
                    oldAvg = self.longHistory[i][-1]
                    self.longHistory[i][-1] = float(count * oldAvg + newData[i]) / (count + 1)
                count += 1
            elif len(self.longHistory[0]) < self.historyLength:
                # Need to add a new point and there is room for it.
                for i in range(nCols):
                    self.longHistory[i].append(newData[i])
                count = 1
            else:
                # Need to add a new point but that would exceed max length.
                # Cut the array in half.
                newView = [[float(col[2*i] + col[2*i+1]) / 2. 
                            for i in range(self.historyLength / 2)] 
                            for col in self.longHistory]
                if self.historyLength % 2:
                    for col in range(nCols):
                        newView[col].append(float(self.longHistory[col][-1] + newData[col]) / 2)
                    count = 2
                else:
                    for col in range(nCols):
                        newView[col].append(newData[col])
                    count = 1
                denom *= 2
                self.longHistory = newView


class Acquirer(StartStopThread):
    def __init__(self, period, daqFunc, callbackFunc):
        super(Acquirer, self).__init__()
        self.period = period
        self.daqFunc = daqFunc
        self.callbackFunc = callbackFunc
        self.last = None

    def run(self):
        tLast = 0
        t0 = time.time()
        while self.runFlag:
            tNow = time.time()
            if tNow >= tLast + self.period:
                data = self.daqFunc()
                tLast = tNow
                self.last = data
                if not isinstance(data, Container):
                    data = (data,)
                self.callbackFunc(tNow, *data)
            time.sleep(0.01)

 
def test():
    import random
    dh = DataHandler()
    dh.start()

    dummySource = lambda: random.randint(0, 100)
    daq = Acquirer(1, dummySource, dh.addToQueue)
    daq.start()

    plotter = Plotter(5, dh.getLongHistory)
    plotter.start()

    return (plotter, daq, dh)
    