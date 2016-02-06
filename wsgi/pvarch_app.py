#!/usr/bin/env python

import sys
from time import time, localtime, strftime

from flask import (Flask, request, session, redirect, url_for,
                   abort, render_template, flash, Response)

from werkzeug import secure_filename


import numpy as np
from epics import PV
from EpicsArchiver import config
from EpicsArchiver.SimpleDB import Connection
from WebStatus import WebStatus

from archive import ArchiveMaster, parse_times, convert_string_data

from make_plot import make_plot

from secret import secret_key
import sys
sys.path.insert(0, config.template_dir)

from pages import pagelist, filemap

app = Flask(__name__)
app.config.from_object(__name__)
app.debug = True

app.secret_key = secret_key
app.config['SESSION_TYPE'] = 'memcached'

dbconn = Connection(dbname=config.master_db, user=config.dbuser,
                    passwd=config.dbpass, host=config.dbhost)

arch = ArchiveMaster(user=config.dbuser, password=config.dbpass)

ago_choices = [{'val':'15_minutes', 'label':'15 minutes'},
               {'val':'30_minutes', 'label':'30 minutes'},
               {'val':'1_hours', 'label':'1 hour'},
               {'val':'3_hours', 'label':'3 hours'},
               {'val':'6_hours', 'label':'6 hours'},
               {'val':'12_hours', 'label':'12 hours'},
               {'val':'1_days', 'label':  '1 day'},
               {'val':'2_days', 'label':  '2 days'},
               {'val':'3_days', 'label':  '3 days'},
               {'val':'7_days', 'label':  '1 week'},
               {'val':'14_days', 'label': '2 weeks'},
               {'val':'21_days', 'label': '3 weeks'},
               {'val':'42_days', 'label': '6 weeks'}]



@app.route('/')
def index():
    return redirect(url_for('show', page='General'))


@app.route('/help')
def help():
    return render_template('help.html')    

@app.route('/admin')
@app.route('/admin/<option>')
def admin(option=None):
    return Response(arch.status_report())

@app.route('/show/<page>')
def show(page=None):
    """
    Could be translated to static pages ?
    """
    p = WebStatus(cache=None, dbconn=dbconn)
    page = str(page)
    
    p.begin_page(page, pagelist, refresh=60)
    
    template = filemap[page]
    if template.startswith('<'):
        method = template[1:-1]
        try:
            getattr(p,method)()
        except:
            pass
    else:
        p.show_pvfile(template)
   
    p.end_page()
    return Response(p.get_buffer())

@app.route('/data/<pv>/<timevar>/<date1>')
@app.route('/data/<pv>/<timevar>/<date1>/<date2>')
@app.route('/data/<pv>/<timevar>/<date1>/<date2>/<extra>')
def data(pv=None, timevar=None, date1=None, date2=None, extra=None):

    if date1 is not None and date1.endswith('.dat'): date1 = None
    if date2 is not None and date2.endswith('.dat'): date2 = None
    
    tmin, tmax, date1, date2, time_ago = parse_times(timevar, date1, date2)
    ts, dat = arch.get_data(pv, tmin=tmin, tmax=tmax, with_current=True)

    
    stmin = strftime("%Y-%m-%d %H:%M:%S", localtime(tmin))
    stmax = strftime("%Y-%m-%d %H:%M:%S", localtime(tmax))
    
    pvinfo  = arch.get_pvinfo(pv)

    buff = ['# Data for %s [%s] '      % (pv, pvinfo['desc']),
            '# Time Range: %s , %s'   % (stmin, stmax),
            '# Timestamps: [%.1f : %.1f]' % (tmin, tmax),
            '# Data Type: %s'           % pvinfo['type']]

    fmt = '%13.7g'
    if pvinfo['type'] == 'enum':
        thispv = PV(pv)
        thispv.get()
        fmt = '%13i'
        buff.append('# Value Meanings:')
        for _i, _enum in enumerate(thispv.enum_strs):
            buff.append('#   %i: %s' % (_i, _enum))

    if dat.dtype.type == np.string_:
        dat = convert_string_data(dat)
        fmt = '%s'
            
    buff.append('#---------------------------------------------------')
    buff.append('# TimeStamp        Value       Date      Time')
    for _t, _v in zip(ts, dat):
        try:
            val = fmt % _v
        except:
            val = repr(_v)
        ddate = strftime("%Y%m%d", localtime(_t))
        dtime = strftime("%H%M%S", localtime(_t))
        buff.append(' %.1f  %s  %s  %s' % (_t, val, ddate, dtime))
    return Response("\n".join(buff), mimetype='text/plain')
    
@app.route('/plot/<pv>')
@app.route('/plot/<pv>/<pv2>')
@app.route('/plot/<pv>/<pv2>/<timevar>')
@app.route('/plot/<pv>/<pv2>/<timevar>/<date1>')
@app.route('/plot/<pv>/<pv2>/<timevar>/<date1>/<date2>')
def plot(pv=None, pv2=None, timevar=None, date1=None, date2=None):

    if pv2     in ('', None, 'None'):
        pv2 = None
        
    if timevar is None:
        timevar = 'time_ago'

    tmin, tmax, date1, date2, time_ago = parse_times(timevar, date1, date2)

    timestr = 'time_ago/%s' % time_ago
    if timevar.startswith('date'):
        timestr = 'date_range/%s/%s' % (date1, date2)
        
    messages = []

    ts, dat, enums, ylabel, ylog = None, None, None, None, False
    try:
        related = arch.related_pvs(pv)
        if len(related) > 25:
            related = related[:25]
        pvinfo  = arch.get_pvinfo(pv)
        desc    = pvinfo['desc']
        dtype   = pvinfo['type']
        if dtype == 'enum':
            thispv = PV(pv)
            thispv.get()
            enums = thispv.enum_strs
            
        ylog    = pvinfo['graph_type'].startswith('log')
        ts, dat = arch.get_data(pv, tmin=tmin, tmax=tmax, with_current=True)
        ylabel  = "%s\n[%s]" % (desc, pv)
    except:
        messages.append("data for '%s' not found" % pv)
        
    ts2, dat2, enums2, y2label, y2log = None, None, None, None, False
    if pv2 is not None:
        try:
            pvinfo2  = arch.get_pvinfo(pv2)
            desc2    = pvinfo2['desc']
            dtype2   = pvinfo2['type']
            if dtype2 == 'enum':
                thispv = PV(pv2)
                thispv.get()
                enums2 = thispv.enum_strs
            y2log    = pvinfo2['graph_type'].startswith('log')
            ts2, dat2 = arch.get_data(pv2, tmin=tmin, tmax=tmax, with_current=True)
            y2label="%s\n[%s]" % (desc2, pv2)
        except:
            messages.append("data for '%s' not found" % pv2)            

    fig, pvdata, pv2data = None, None, None
    if ts is not None:
        if dat.dtype.type == np.string_:
            dat = convert_string_data(dat)
            pvdata = []
            for _t, _d in zip(ts, dat):
                pvdata.append({'ts': strftime("%Y-%m-%d %H:%M:%S", localtime(_t)),
                               'val': _d})
            last_pt = pvdata.pop()
            pvdata.append({'ts': "Now", 'val': last_pt['val']})

        if dat2 is not None and dat2.dtype.type == np.string_:
            dat2 = convert_string_data(dat2)
            pv2data = []
            for _t, _d in zip(ts2, dat2):
                pv2data.append({'ts': strftime("%Y-%m-%d %H:%M:%S", localtime(_t)),
                                'val': _d})
            last_pt = pv2data.pop()
            pv2data.append({'ts': "Now", 'val': last_pt['val']})

        if pvdata is None and pv2data is None:
            fig = make_plot(ts, dat, ylabel=ylabel,
                            enums=enums,  ylog=ylog,
                            ts2=ts2, dat2=dat2, y2label=y2label,
                            enums2=enums2, y2log=y2log,
                            tmin=tmin, tmax=tmax)

    if len(messages) > 0:
        messages = ', '.join(messages)
    else:
        messages = None

    odate1 = odate2 = ''
    if date1 is not None: odate1 = date1
    if date2 is not None: odate2 = date2
    
    opts = {'pv': pv, 'pv2': pv2,
            'pvdata': pvdata, 'pv2data': pv2data,
            'odate1': odate1, 'odate2': odate2,
            'timestr':  timestr,
            'time_ago': time_ago,
            'messages': messages,
            'figure' : fig,
            'related': related,
            'ago_choices':  ago_choices}
    
    return render_template('plot.html', **opts)

@app.route('/formplot', methods=['GET', 'POST'])
def formplot():
    if request.method == 'POST':
        form = request.form
        pv = form.get('pv', 'None')
        pv2 = form.get('pv2', 'None')
        if pv2     in ('', None, 'None'): pv2 = None
        if form.get('submit', 'From Present').lower().startswith('from'):
            date1 = form.get('timevar', '1_days')
            return redirect('plot/%s/%s/time_ago/%s' % (pv, pv2, date1))
        else:
            date1 = form.get('date1', 'None')
            date2 = form.get('date2', 'None')
            return redirect('plot/%s/%s/date_range/%s/%s' % (pv, pv2, date1, date2))
        
    return Response(" Create Plot based on Form Submission(Date Range) %s" %  form.items())




