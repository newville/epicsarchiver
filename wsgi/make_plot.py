import time
import io

import base64

import numpy as np
import matplotlib

matplotlib.use('Agg')
from matplotlib.backends.backend_agg import Figure, FigureCanvas

from matplotlib.font_manager import FontProperties
from matplotlib.ticker import FuncFormatter
from matplotlib import rcParams, dates

import datetime

mplfont = FontProperties()
mplfont.set_size(12)
matplotlib.rc('xtick', labelsize=12)
matplotlib.rc('ytick', labelsize=12)

def tformatter(x, *args, **kws):
    return time.strftime("%H:%M\n%m/%d",
                         dates.num2date(x).timetuple())

def make_plot(ts, ydat, ylabel='Data',
              time_unit='days', time_val=1, fname=None):
    
    tvals  = [datetime.datetime.fromtimestamp(t) for t in ts]
    fig    = Figure(figsize=(8.0, 5.0), dpi=200)
    canvas = FigureCanvas(fig)
    axes   = fig.add_axes([0.14, 0.16, 0.80, 0.80], axisbg='#FFFFFF')

    axes.set_xlabel('Date', fontproperties=mplfont)
    axes.set_ylabel(ylabel, fontproperties=mplfont)
    axes.xaxis.set_major_formatter(FuncFormatter(tformatter))
    for x in axes.get_xticklabels():
        x.set_rotation(0)
        x.set_ha('center')

    axes.plot(tvals, ydat, linewidth=2, 
              marker='s', markersize=3.5,
              drawstyle='steps-post')

    opts = {}
    opts[time_unit] = time_val
    tdelta = datetime.timedelta(**opts)
    tmax = max(tvals)
    axes.set_xlim((tmax-tdelta, tmax), emit=True)

    if fname is not None:
        fig.savefig(fname)
        return
    
    figdata = io.BytesIO()
    fig.savefig(figdata, format='png', facecolor='#FDFDFA')
    figdata.seek(0)
    return base64.b64encode(figdata.getvalue())


arr = np.loadtxt('px.dat')
ts  = arr[:, 2]
val = arr[:, 3]

make_plot(ts, val, ylabel='Xs', time_val=1.003, fname='t.png')

    
#figdata = io.BytesIO()
#fig.savefig(figdata, format='png', facecolor='#FDFDFA')
#figdata.seek(0)
#return base64.b64encode(figdata.getvalue())
