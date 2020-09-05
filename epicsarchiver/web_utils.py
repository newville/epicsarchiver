from time import time, strftime, localtime
from collections import namedtuple
from datetime import datetime, date, timedelta
from dateutil.parser import parse as dateparser
import numpy as np
import json

def isnull(x):
    if x is None:
        x = 'none'
    if isinstance(x, bytes):
        x = x.decode('utf-8')
    x = x.strip().lower()
    return x in ('', 'none')

def null2blank(val):
    if isnull(val):
        return ''
    return val

def ts2iso(ts):
    "timestamp to iso format"
    return strftime("%Y-%m-%dT%H:%M:%S", localtime(ts))

def parse_times(date1, date2):
    """returns 2 datetimes for date1 and date2 values

    Options
    --------
    date1 (string, int, float):  initial date
    date2 (string, int, float):  final date

    Notes:
    ------
    1.  int/float values will be treated as timestamps
    2.  if date2 is 'now', then date1 will be interpreted as
        'time ago', and assumed to be like
               '3.5 hour', '4 days', '3 weeks', '1 year'
        with 'hour', 'day', 'week', and 'year' (and plurals) all
        converted to an integer number of hours, and the rest of
        the string treated as a float.

        with date2='now', an unrecognized value for date1 with give '1week'

    3. otherwise the the two date values should be strings of the form
           "%Y-%m-%d %H:%M:%S"
       or a related string that can be parsed by dateutil.parser.parse.
    4. time is truncated to the nearest second
   """
    if isinstance(date1, (float, int)):
        date1 = ts2iso(date1)
    if isinstance(date2, (float, int)):
        date2 = ts2iso(date2)

    date1 = '1week' if isnull(date1) else date1.lower()
    date2 = 'now'   if isnull(date2) else date2.lower()

    if date2 == 'now':
        date1 = date1.lower()
        hago = 168
        if 'hour' in date1:
            hago =    1 * float(date1.replace('hours', '').replace('hour', ''))
        elif 'day' in date1:
            hago =   24 * float(date1.replace('days', '').replace('day', ''))
        elif 'week' in date1:
            hago =  168 * float(date1.replace('weeks', '').replace('week', ''))
        elif 'year' in date1:
            hago = 8760 * float(date1.replace('years', '').replace('year', ''))

        now = time()
        dt1 = datetime.fromtimestamp(now - 3600.0*hago)
        dt2 = datetime.fromtimestamp(now)
    else:
        if '.' in date1:
            date1 = date1[:date1.index('.')]
        if '.' in date2:
            date2 = date2[:date2.index('.')]
        dt1 = dateparser(date1)
        dt2 = dateparser(date2)

    return (dt1, dt2)


def chararray_as_string(val):
    """convert numpy string arrays for Waveform PVs to strings"""
    tval = val[:]
    for c in ('\n', '\r', '[', ']', '(', ')', ','):
        tval = tval.replace(c, '')
    try:
        val = [int(i) for i in tval.split()]
    except:
        return val
    val.append(0)
    return ''.join([chr(int(i)) for i in val[:val.index(0)]])



def auto_ylog(vals):
    """
    decide whether a list of values should be displayed on a ylog scale
    this removes values very nearly 0 (<1.e-150) and then sees whether
    the 1 to 99th percentiles varies by more than a factor of 200.0
    """
    x = np.array(vals)

    xmin = x.min()
    if xmin < 0:
        return False

    x01, x99 = np.percentile(x[np.where(x>1.e-150)], [1, 99])
    return (x99 > 200*x01)


## if ylog_scale:
#         ytype = 'log'
#         ymax = np.log10(y).max()
#         ymin = max(np.log10(y).min(), -9)
#         if y2 is not None:
#             ymin = min(np.log10(y2).min(), ymin)
#             ymax = max(np.log10(y2).max(), ymax)
#         if yrange is None:
#             yrange = (ymin-0.5, ymax+0.5)
    # if yrange is not None:
    #     layout['yaxis']['range'] = yrange

# plotly modeBarButtons:
## - '2D': zoom2d, pan2d, select2d, lasso2d, zoomIn2d, zoomOut2d, autoScale2d, resetScale2d
## -'3D': zoom3d, pan3d, rbitRotation, tableRotation, handleDrag3d, resetCameraDefault3d, resetCameraLastSave3d, hoverClosest3d
## -'Cartesian': hoverClosestCartesian, hoverCompareCartesian
## -'Geo': zoomInGeo, zoomOutGeo, resetGeo, hoverClosestGeo
## -'Other': hoverClosestGl2d, hoverClosestPie, toggleHover, resetViews, toImage: sendDataToCloud, toggleSpikelines, resetViewMapbox

PlotData = namedtuple('PlotData', ('t', 'y', 'pvname', 'label',
                                   'force_ylog', 'enum_labels'))

pcolors = ('#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
           '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf')

def make_plot(plotdata, size=(725, 625)):
    """make plotly plot from a list of PlotData tuples
    """
    data = []
    title = None
    ntraces = len(plotdata)
    domwid = 1.07 - 0.09*(ntraces-1)
    layout = {'width': size[0], 'height': size[1],
              'hovermode': 'closest',
              'showlegend': True,
              'bgcolor':'#FAFAFA',
              'legend': {'borderwidth': 0.5, 'bgcolor':'#F0F0F0',
                         'orientation': 'h',
                         'x': 0.05, 'y': 1.10, 'yanchor': 'top',
                         },
              'xaxis': {'title': {'text': 'Date'},
                        'domain': [0.02, domwid]}}
    for trace, this in enumerate(plotdata):
        ykey = 'y%d' % (trace+1) if trace>0 else 'y'
        data.append({'x':[ts2iso(ts) for ts in this.t],
                     'y': this.y,
                     'name': this.pvname,
                     'mode': 'lines+markers',
                     'yaxis': ykey,
                     'line': {'width': 3, 'shape': 'hv'}})



        yax = {'title': {'text': this.label, 'color': pcolors[trace]},
               'zeroline': False,  'type': 'linear',
               'titlefont': {'color': pcolors[trace]},
               'tickfont':  {'color': pcolors[trace]}}

        if this.force_ylog or auto_ylog(this.y):
            yax.update({'type':  'log', 'tickformat': '.3g'})


        if this.enum_labels is not None:
            yax.update({'ticktext': this.enum_labels,
                        'tickvals': list(range(len(this.enum_labels)))})

        if trace > 0:
            print("trace,  ", domwid, domwid+0.09*(trace-1))
            yax.update({'anchor': 'free',
                        'title': this.label,
                        'showgrid': False,
                        'overlaying': 'y',
                        'side': 'right',
                        'position': domwid+0.09*(trace-1)})

        yl = ykey.replace('y', 'yaxis')
        layout[yl] = yax

    config = {'displaylogo': False,
              'modeBarButtonsToRemove': ['hoverClosestCartesian',
                                         'hoverCompareCartesian',
                                         'toggleSpikelines', 'pan2d',
                                         'select2d', 'lasso2d']}

    return json.dumps({'data': data, 'layout': layout, 'config': config})
