import time
import io

import base64

import numpy as np
import matplotlib

matplotlib.use('Agg')
from matplotlib.backends.backend_agg import Figure, FigureCanvas

from matplotlib.gridspec import GridSpec
from matplotlib.font_manager import FontProperties
from matplotlib.ticker import FuncFormatter
from matplotlib import rcParams, dates

import datetime

mplfont = FontProperties()
mplfont.set_size(12)
mplfont.set_weight('semibold')

matplotlib.rc('xtick', labelsize=12)
matplotlib.rc('ytick', labelsize=12)
matplotlib.rc('grid',  linewidth=0.5, color='#E7E7E7', linestyle='-')
matplotlib.rc('savefig', dpi=150)

plotopts = dict(linewidth=1.5, marker='s', 
    markersize=3.5, markeredgewidth=0.0, 
    drawstyle='steps-post', zorder=30)


def tformatter(x, *args, **kws):
    return time.strftime("%H:%M\n%m/%d",
                         dates.num2date(x).timetuple())

def auto_margins(fig, canvas, axes, gspec):
    """automatically set margins"""    
    trans = fig.transFigure.inverted().transform
    l, t, r, b, dl, dt, dr, db = [0.025]*8
    for ax in fig.get_axes():
        (x0, y0), (x1, y1) = ax.get_position().get_points()
        gpoints = ax.get_tightbbox(canvas.get_renderer()).get_points()
        (w0, h0), (w1, h1) = gpoints
        (w0, h0), (w1, h1) = trans(((w0 ,h0),(w1 ,h1)))
        dl = max(dl, (x0 - w0))
        dt = max(dt, (h1 - y1))
        dr = max(dr, (w1 - x1))
        db = max(db, (y0 - h0))
    gspec.update(left=l+dl, top=1-(t+dt), right=1-(r+dr), bottom=b+db)
    for ax in fig.get_axes():
        ax.update_params()
        ax.set_position(ax.figbox)

def make_plot(ts, dat, ylabel='Data', ylog=False, 
              ts2=None, dat2=None, y2label=None, y2log=False, 
              time_unit='days', time_val=1, fname=None):
   
    fig    = Figure(figsize=(8., 5.0), dpi=300)
    gspec  = GridSpec(1, 1)
    canvas = FigureCanvas(fig)
    axes   = fig.add_subplot(gspec[0], axisbg='#FFFFFF')

    axes.set_xlabel('Date', fontproperties=mplfont)
    axes.xaxis.set_major_formatter(FuncFormatter(tformatter))
    for x in axes.get_xticklabels():
        x.set_rotation(0)
        x.set_ha('center')

        
    tvals  = [datetime.datetime.fromtimestamp(t) for t in ts]
    axes.set_ylabel(ylabel, color='b', fontproperties=mplfont)

    if ylog:
        axes.set_yscale('log', basey=10)        
    axes.plot(tvals, dat, color='b', **plotopts)
    axes.grid(True)
    
    if ts2 is not None:
        t2vals  = [datetime.datetime.fromtimestamp(t) for t in ts2]
        if len(fig.get_axes()) < 2:
            ax = axes.twinx()
        axes = fig.get_axes()[1]
        if y2log:
            axes.set_yscale('log', basey=10)
        plotopts['zorder'] = 25
        axes.plot(t2vals, dat2, color='r', **plotopts)
        axes.set_ylabel(y2label, color='r', fontproperties=mplfont)
    
    opts = {}
    opts[time_unit] = time_val
    tdelta = datetime.timedelta(**opts)
    tmax = max(tvals)
    axes.set_xlim((tmax-tdelta, tmax), emit=True)

    auto_margins(fig, canvas, axes, gspec)
    if fname is None:
        figdata = io.BytesIO()
        fig.savefig(figdata, format='png', facecolor='#FDFDFA')
        figdata.seek(0)
        return base64.b64encode(figdata.getvalue())
    else:
        fig.savefig(fname)
        
        return fname
    

###
if __name__ == '__main__':
    arr1 = np.loadtxt('p2.dat')
    x1 = arr1[:,2]
    y1 = arr1[:,3]
    d1 = 'desc for PV2\n[PV1]'
    
    arr2 = np.loadtxt('p1.dat') 
    x2 = arr2[:,2]
    y2 = arr2[:,3]   
    d2 = 'desc for PV2\n[PV2]'



    make_plot(x1, y1, ylabel=d1, 
              ts2=x2, dat2=y2, y2label=d2,
              time_val=1.0, fname='t.png')
