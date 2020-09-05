from time import time, mktime, strftime
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

def parse_times(date1='1 week', date2=None):

    """returns 2 datetimes for date1 and date2 values

    Options
    --------
    date1 (string):          string for initial date ['1 week']
    date2 (string or None):  string for final date [None]

    Notes:
    ------
    1.  if date2 is '', None, or 'None' then the meaning is "from now", and
        the date1 string can be like
               '3.5 hour', '4 days', '3 weeks', '1 year'
        with 'hour', 'day', 'week', and 'year' (and plurals) all understood
        in terms of an integer number of hours, and the rest of the string
        treated as a float.

    2. otherwise the the two date values should be strings of the form
           "%Y-%m-%d %H:%M:%S"
       or a related string that can be parsed by dateutil.parser.parse.
    """
    date1 = '1week' if isnull(date1) else date1.lower()
    date2 = 'none'  if isnull(date2) else date2.lower()

    if isnull(date2):
        date1 = date1.lower()
        h_ago = 168
        if 'hour' in date1:
            h_ago =    1 * float(date1.replace('hours', '').replace('hour', ''))
        elif 'day' in date1:
            h_ago =   24 * float(date1.replace('days', '').replace('day', ''))
        elif 'week' in date1:
            h_ago =  168 * float(date1.replace('weeks', '').replace('week', ''))
        elif 'year' in date1:
            h_ago = 8760 * float(date1.replace('years', '').replace('year', ''))

        now = time()
        dt1 = datetime.fromtimestamp(int(now - 3600.0*h_ago))
        dt2 = datetime.fromtimestamp(int(now))
    else: # provided start/stop times
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


def make_plot(pvdata, size=(700, 500)):
    """make plotly plot from pvdata:
    (ts, y, label, ylog, dtype, enums, current_t, current_y)
    """
    data = []
    title = None
    for pv, t, y, label, ylog, dtype, enums, ct, cy in pvdata:
        data.append({'x':[datetime.fromtimestamp(t_).isoformat() for t_ in t],
                     'y': y,
                     'name': label,
                     'mode': 'lines+markers',
                     'line': {'width': 3, 'shape': 'hv'}})
        if title is None:
            title = pv

    layout = {'title': title, 'width': size[0], 'height': size[1],
              'showlegend': len(data) > 1,
              'hovermode': 'closest',
              'xaxis': {'title': {'text': 'Date'}, 'type': 'date'},
              'yaxis': {'title': {'text': label},
                        'zeroline': False,'type': 'linear'}  }


    config = {'displaylogo': False,
              'modeBarButtonsToRemove': ['hoverClosestCartesian','hoverCompareCartesian',
                                         'toggleSpikelines', 'pan2d', 'select2d', 'lasso2d']}

    return json.dumps({'data': data, 'layout': layout, 'config': config})
