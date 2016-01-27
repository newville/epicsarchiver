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

plotopts = dict(linewidth=2.0, marker='s', 
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

def make_plot(ts, dat, ylabel='Data', ylog=False, enums=None,
              ts2=None, dat2=None, y2label=None, y2log=False,
              enums2=None, time_unit='days', time_val=None, fname=None):
   
    fig    = Figure(figsize=(8., 5.0), dpi=300)
    gspec  = GridSpec(1, 1)
    canvas = FigureCanvas(fig)
    axes   = fig.add_subplot(gspec[0], axisbg='#FFFFFF')

    axes.set_xlabel('Date', fontproperties=mplfont)
    axes.xaxis.set_major_formatter(FuncFormatter(tformatter))
    for x in axes.get_xticklabels():
        x.set_rotation(0)
        x.set_ha('center')

    axes.set_ylabel(ylabel, color='b', fontproperties=mplfont)

    # if time range / units is set, limit data
    tmin = None
    tmax = None
    if time_val is not None and time_unit is not None:
        opts = {}
        opts[time_unit] = int(time_val)
        dt_max = datetime.datetime.fromtimestamp(max(ts))
        dt_min = dt_max - datetime.timedelta(**opts)
        tmin = time.mktime(dt_min.timetuple())
        tmax = max(ts)
        sel = np.where(ts>=tmin)
        older= np.where(np.logical_and(ts>tmin-86400, ts<tmin))
        if len(older[0]) > 0:
            sel = np.concatenate(([older[0][-1]], sel[0]))
        ts  = ts[sel]
        dat = dat[sel]
    
    tvals  = [datetime.datetime.fromtimestamp(t) for t in ts]
    if tmin is None:
        tmin = min(ts)
    if tmax is None:
        tmax = max(ts)        
        
    if ylog:
        axes.set_yscale('log', basey=10)
        pos = np.where(dat>0)
        ts  = ts[pos]
        dat = dat[pos]

    if enums is not None:
        pad = min(0.8, 0.1*len(enums))
        axes.set_ylim(-pad, len(enums)-1+pad)
        axes.set_yticks(range(len(enums)))
        axes.set_yticklabels(enums)
    axes.get_yaxis().get_major_formatter().set_useOffset(False)
    axes.plot(tvals, dat, color='b', **plotopts)
    axes.set_xlim((datetime.datetime.fromtimestamp(tmin),
                     datetime.datetime.fromtimestamp(tmax)), emit=True)
    axes.grid(True)
    
    if ts2 is not None:
        if len(fig.get_axes()) < 2:
            ax = axes.twinx()
        axes = fig.get_axes()[1]
        axes.get_yaxis().get_major_formatter().set_useOffset(False)        
        if y2log:
            axes.set_yscale('log', basey=10)
            pos = np.where(dat2>0)
            ts2 = ts2[pos]
            dat2 = dat2[pos]
        if tmin is not None:
            sel = np.where(ts2>=tmin)
            older= np.where(np.logical_and(ts2>tmin-86400, ts2<tmin))
            if len(older[0]) > 0:
                sel = np.concatenate(([older[0][-1]], sel[0]))
            ts2 = ts2[sel]
            dat2 = dat2[sel]
        t2vals  = [datetime.datetime.fromtimestamp(t) for t in ts2]
        plotopts['zorder'] = 25
        if enums2 is not None:
            pad = min(0.8, 0.1*len(enums2))
            axes.set_ylim(-pad, len(enums2)-1+pad)
            axes.set_yticks(range(len(enums2)))
            axes.set_yticklabels(enums2)

        axes.plot(t2vals, dat2, color='r', **plotopts)
        axes.set_ylabel(y2label, color='r', fontproperties=mplfont)
    
    auto_margins(fig, canvas, axes, gspec)
    if fname is None:
        figdata = io.BytesIO()
        fig.savefig(figdata, format='png', facecolor='#FDFDFA')
        figdata.seek(0)
        return base64.b64encode(figdata.getvalue())
    else:
        fig.savefig(fname)
        return fname
    

