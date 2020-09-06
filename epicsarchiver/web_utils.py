from time import time, mktime, strftime
from datetime import datetime, date, timedelta
from dateutil.parser import parse as dateparser
import numpy as np
import json

from .util import normalize_pvname

def parse_times(date1='1 week', date2=None):

    """returns 2 datetimes for date1 and date2 values

    Options
    --------
    date1 (string):          string for initial date ['1 week']
    date2 (string or None):  string for final date [None]

    Notes:
    ------
    1.  if date2 is '', None, or 'None' then the meaning "from now", and
        the date1 string can be like
               '3.5 hour', '4 days', '3 weeks', '1 year'
        with 'hour', 'day', 'week', and 'year' (and plurals) all understood
        in terms of an integer number of hours, and the rest of the string
        treated as a float.

    2. otherwise the the two date values should be strings of the form
           "%Y-%m-%d %H:%M:%S"
       or a related string that can be parsed by dateutil.parser.parse.
    """
    date1 = 'day'  if date1 in ('', None) else date1.lower()
    date2 = 'none' if date2 in ('', None) else date2.lower()

    if date2 in ('', 'none'): # time ago
        if 'hour' in date1:
            factor = 1
            date1 = float(date1.replace('hour', '').replace('hours', ''))
        elif 'day' in date1:
            factor = 24
            date1 = float(date1.replace('day', '').replace('days', ''))
        elif 'week' in date1:
            factor = 24*7
            date1 = float(date1.replace('week', '').replace('weeks', ''))
        elif 'year' in date1:
            factor = 24*365
            date1 = float(date1.replace('year', '').replace('years', ''))
        now = time()
        dt1 = datetime.fromtimestamp(now - 3600*factor*date1)
        dt2 = datetime.fromtimestamp(now)
    else: # provided start/stop times
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



#
#     if ylog_scale:
#         ytype = 'log'
#         ymax = np.log10(y).max()
#         ymin = max(np.log10(y).min(), -9)
#         if y2 is not None:
#             ymin = min(np.log10(y2).min(), ymin)
#             ymax = max(np.log10(y2).max(), ymax)
#         if yrange is None:
#             yrange = (ymin-0.5, ymax+0.5)

def make_plot(pvdata, ignore_last_point=True):
    """make plotly plot from pvdata:
    (ts, y, label, ylog, dtype, enums, current_t, current_y)
    """
    data = []
    title = None
    for pv, t, y, label, ylog, dtype, enums, ct, cy in pvdata:

        data.append({'x':[datetime.fromtimestamp(t_) for t_ in t],
                     'y': y,
                     'name': label,
                     'mode': 'lines+markers',
                     'line': {'width': 3, 'shape': 'hv'}})

        if title is None:
            title = pv

    layout = {'title': title,
              'height': 475,
              'width': 600,
              'showlegend': len(data) > 1,
              'hovermode': 'closest',
              'xaxis': {'title': {'text': 'Date'}, 'type': 'date'},
              'yaxis': {'title': {'text': label},
                        'zeroline': False,'type': 'linear'},
              }


    # if yrange is not None:
    #     layout['yaxis']['range'] = yrange

    config = {'displaylogo': False,
              'modeBarButtonsToRemove': [ 'hoverClosestCartesian',
                                          'hoverCompareCartesian',
                                          'toggleSpikelines']}


    return to_json({'data': data,
                    'layout': layout,
                    'config': config})



###
###
html_top = """{% extends "layout.html" %}
{% block body %}

<table>
"""

html_bottom = """</table>
{% endblock %}
"""

html_label  = " <tr><td class='section'>  %s </td><td></td></tr> "
html_hr     = " <tr><td colspan=2><hr></td></tr> "
html_space  = " <tr><td colspan=2>&nbsp;</td></tr> "
html_pvrow  = """
  <tr><td class='pvlabel'> %s </td>
      <td class='pvlink'> %s </td>
  </tr>"""

showpv = " {{ showpv('%s') }} "
def tmpl2jinja(file):
    with open(file, "r") as fh:
        lines = fh.readlines()
        
    buff = [html_top]
    for line in lines:
        line = line[:-1].strip()
        if line.startswith('#') or len(line) < 2:
            continue
        elif line.startswith('['):
            i = line.find(']')
            if i == -1:
                i= len(line)
            buff.append(html_label % (line[1:i]))

            
        elif line.startswith('--'):
            buff.append(html_hr)
        elif line.startswith('<>'):
            buff.append(html_space)
        else:
            words = [w.strip() for w in line.split('|')]
 
            pvnames = words.pop(0)
            pvnames = [normalize_pvname(w.strip()) for w in pvnames.split(',')]
            desc, format, outtype = None, None, None

            if len(words) > 0:
                desc = words.pop(0).strip()
                if len(desc) == 0:
                    desc = None
                if len(words) > 0:
                    format = words.pop(0).strip()
            if format == 'yes/no':
                format = None
                outtype = 'yes/no'

            pvlinks = ', '.join([showpv % n for n in pvnames])
            buff.append(html_pvrow % (desc, pvlinks))

    buff.append(html_bottom)
    return '\n'.join(buff)



