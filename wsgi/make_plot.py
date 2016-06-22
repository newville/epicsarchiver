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
from matplotlib import rcParams
from matplotlib.dates import DateFormatter, num2date
from matplotlib.dates import AutoDateFormatter, AutoDateLocator

from datetime import datetime

ts2date = datetime.fromtimestamp

mplfont = FontProperties()
mplfont.set_size(11)
mplfont.set_weight('semibold')

matplotlib.rc('xtick', labelsize=10)
matplotlib.rc('ytick', labelsize=10)
matplotlib.rc('grid',  linewidth=0.5, color='#EDEDED', linestyle='-')
matplotlib.rc('savefig', dpi=150)

plotopts = dict(linewidth=2.0, marker='s',
                markersize=3.5, markeredgewidth=0.0,
                drawstyle='steps-post', zorder=25)

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
              ts2=None, dat2=None, y2label=None,
              y2log=False,  enums2=None,
              tmin=None, tmax=None, fname=None,
              ymin=None, ymax=None, y2min=None, y2max=None):

    fig    = Figure(figsize=(8., 5.0), dpi=300)
    gspec  = GridSpec(1, 1)
    canvas = FigureCanvas(fig)
    axes   = fig.add_subplot(gspec[0], axisbg='#FFFFFF')


    if ylog: #  and False:
        axes.set_yscale('log', basey=10)
        pos = np.where(dat>0)
        ts  = ts[pos]
        dat = dat[pos]

    tvals  = [ts2date(t) for t in ts]

    if enums is not None:
        pad = min(0.8, 0.1*len(enums))
        axes.set_ylim(-pad, len(enums)-1+pad)
        axes.set_yticks(range(len(enums)))
        axes.set_yticklabels(enums)

    try:
        axes.get_yaxis().get_major_formatter().set_useOffset(False)
    except:
        pass


    if tmin is not None and tmax is not None:
        axes.set_xlim((ts2date(tmin), ts2date(tmax)))
    if ymin is not None or ymax is not None:
        if ymin is not None:
            ymin = float(ymin)
        else:
            ymin = min(dat)
        if ymax is not None:
            ymax = float(ymax)
        else:
            ymax = max(dat)
        axes.set_ylim((ymin, ymax))

    axes.set_xlabel('Date', fontproperties=mplfont)
    axes.set_ylabel(ylabel, color='b', fontproperties=mplfont)
    axes.xaxis.set_major_formatter(DateFormatter("%H:%M\n%b-%d"))
    axes.plot(tvals, dat, color='b', **plotopts)
    for x in axes.get_xticklabels():
        x.set_rotation(0)
        x.set_ha('center')

    axes.grid(True, zorder=-5)


    if ts2 is not None:
        if len(fig.get_axes()) < 2:
            ax = axes.twinx()
        axes = fig.get_axes()[1]
        axes0 = fig.get_axes()[0]
        axes0.set_zorder(axes.get_zorder()+10)
        axes0.patch.set_visible(False)
        axes0.grid(axes.get_zorder()-5)
        axes.grid(False)
        try:
            axes.get_yaxis().get_major_formatter().set_useOffset(False)
        except:
            pass

        if y2log:
            axes.set_yscale('log', basey=10)
            pos = np.where(dat2>0)
            ts2 = ts2[pos]
            dat2 = dat2[pos]
        t2vals  = [ts2date(t) for t in ts2]
        if enums2 is not None:
            pad = min(0.8, 0.1*len(enums2))
            axes.set_ylim(-pad, len(enums2)-1+pad)
            axes.set_yticks(range(len(enums2)))
            axes.set_yticklabels(enums2)
        plotopts['zorder'] = 20
        axes.plot(t2vals, dat2, color='r', **plotopts)
        axes.set_ylabel(y2label, color='r', fontproperties=mplfont)
        if tmin is not None and tmax is not None:
            axes.set_xlim((ts2date(tmin), ts2date(tmax)))

        if y2min is not None or y2max is not None:
            if y2min is not None:
                y2min = float(y2min)
            else:
                y2min = min(dat2)
            if y2max is not None:
                y2max = float(y2max)
            else:
                y2max = max(dat2)

            axes.set_ylim((y2min, y2max))


    auto_margins(fig, canvas, axes, gspec)
    if fname is None:
        figdata = io.BytesIO()
        fig.savefig(figdata, format='png', facecolor='#FDFDFA')
        figdata.seek(0)
        return base64.b64encode(figdata.getvalue())
    else:
        fig.savefig(fname)
        return fname
