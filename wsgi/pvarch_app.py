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

from archive import (ArchiveMaster, parse_times, convert_string_data,
                     __version__, alert_ops)

from make_plot import make_plot

from secret import secret_key, admin_username, admin_password
import sys
sys.path.insert(0, config.template_dir)

from pages import pagelist, filemap

app = Flask(__name__)
app.config.from_object(__name__)
app.debug = True

app.secret_key = secret_key
# app.config['SESSION_TYPE'] = 'memcached'

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


def session_init(session):
    if 'is_admin' not in session:
        session['is_admin'] = False

def toNone(val):
    if val in ('', 'None', None):
        val = None
    return val

@app.route('/')
def index():
    return redirect(url_for('show', page='General'))

@app.route('/help')
def help():
    config.pvdat1 = config.dat_format % (config.dat_prefix, 1)
    config.pvdat2 = config.dat_format % (config.dat_prefix, 2)
    config.pvdat128 = config.dat_format % (config.dat_prefix, 128)
    return render_template('help.html', version=__version__, config=config)

@app.route('/status')
def status():
    session_init(session)
    return render_template('status.html',
                           status=arch.status_report(),
                           admin=session['is_admin'])                           

@app.route('/alerts')
def alerts():
    session_init(session)
    return render_template('alerts.html',
                           alerts=arch.get_alerts(),
                           admin=session['is_admin'],
                           alert_choices=alert_ops)




@app.route('/editalert/<int:alertid>')
def editalert(alertid=None):
    session_init(session)
    alerts=arch.get_alerts()
    thisalert = None
    for a in alerts:
        if a.id == alertid:
            thisalert = a
            
    if thisalert is None or not session['is_admin']:
        return render_template('alerts.html',
                               admin=session['is_admin'],
                               alert_choices=alert_ops)

    return render_template('editalert.html',
                           updated=False,
                           admin=session['is_admin'],
                           alert=thisalert,
                           alert_choices=alert_ops)

@app.route('/submit_alertedits', methods=['GET', 'POST'])
def submit_alertedits(options=None):
    session_init(session)
    
    if request.method == 'POST':
        alertid  = int(request.form['alertid'])
        submit   = 'submit' in request.form.keys()
        makecopy = 'copy' in request.form.keys()
        name     = request.form['name']
        pvname   = request.form['pvname']
        compare  = request.form['compare']
        trippoint= request.form['trippoint']
        active   = request.form['active']
        mailto   = request.form['mailto']
        mailmsg  = request.form['mailmsg']
        timeout  = request.form['timeout']

        alerts = arch.get_alerts()
        for a in alerts:
            if a.id == alertid:
                thisalert = a

        print(" ALERT ", alertid, name, pvname, compare)
        
                
        if makecopy:
            arch.add_alert(pvname=pvname, name="%s (copy)" % name,
                           mailto=mailto, mailmsg=mailmsg, timeout=timeout,
                           compare=compare, trippoint=trippoint)
        else:
            arch.update_alert(alertid=alertid, pvname=pvname, name=name,
                              mailto=mailto, mailmsg=mailmsg, timeout=timeout,
                              compare=compare, trippoint=trippoint)
            
            
                
        return render_template('editalert.html',
                               updated=submit,
                               copied=makecopy,
                               admin=session['is_admin'],
                               alert=thisalert,
                               alert_choices=alert_ops)


    
@app.route('/admin')
@app.route('/admin/<option>')
def admin(option=None):
    session_init(session)    
    return render_template('admin.html',
                           admin=session['is_admin'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    session_init(session)
    session['username'] = None
    session['is_admin'] = False
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if (username.lower() == admin_username and
            admin_password == password):
            session['is_admin'] = True
            session['username'] = username

    if session['username'] is not None:
        return redirect(url_for('show', page='General'))
    else:
        return render_template('login.html')

@app.route('/logout')
def logout():
    session_init(session)
    session['is_admin'] = False
    return redirect(url_for('show', page='General'))
    
@app.route('/show/<page>')
def show(page=None):
    """
    Could be translated to static pages ?
    """
    session_init(session)
    admin = session['is_admin']
    p = WebStatus(cache=None, dbconn=dbconn, admin=admin)
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
    session_init(session)
    admin = session['is_admin']

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
def plot(pv=None, pv2=None, timevar=None, date1=None, date2=None,
         pvmin=None, pvmax=None, pv2min=None, pv2max=None, fdat=None):

    if pv2  in ('', None, 'None'):
        pv2 = None

    if timevar is None:
        timevar = 'time_ago'
    sdate1 = date1
    tmin, tmax, date1, date2, time_ago = parse_times(timevar, date1, date2)

    timestr = 'time_ago/%s' % time_ago
    if timevar.startswith('date'):
        timestr = 'date_range/%s/%s' % (date1, date2)

    messages = []
    pvcurrent, pv2current = None, None
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
        pvcurrent = "%g" % dat[-1]
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
            pv2current = "%g" % dat2[-1]
        except:
            messages.append("data for '%s' not found" % pv2)


        try:
            arch.set_pair_score(pv, pv2)
        except:
            messages.append(" could not increment pair score ")

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
                            tmin=tmin, tmax=tmax,
                            ymin=pvmin, ymax=pvmax,
                            y2min=pv2min, y2max=pv2max)

    if len(messages) > 0:
        messages = ', '.join(messages)
    else:
        messages = None

    # if pv2   is None: pv2 = ''
    if date1 is None: date1 = ''
    if date2 is None: date2 = ''
    if pvmin is None: pvmin = ''
    if pvmax is None: pvmax = ''
    if pv2min is None: pv2min = ''
    if pv2max is None: pv2max = ''

    if fdat is None: fdat = {}

    opts = {'pv': pv,
            'pv2': pv2,
            'pvcurrent': pvcurrent,
            'pv2current': pv2current,
            'pvdata': pvdata,
            'pv2data': pv2data,
            'pvmin': pvmin,
            'pvmax': pvmax,
            'pv2min': pv2min,
            'pv2max': pv2max,
            'fdat': fdat,
            'date1': date1,
            'date2': date2,
            'sdate1': date1,
            'timestr':  timestr,
            'timevar': timevar,
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
        pv = toNone(form.get('pv', ''))
        pv2 = toNone(form.get('pv2', ''))
        pvmin = toNone(form.get('pvmin', ''))
        pvmax = toNone(form.get('pvmax', ''))
        pv2min = toNone(form.get('pv2min', ''))
        pv2max = toNone(form.get('pv2max', ''))
        fdat =  form.items()
        # return render_template('showvars.html', **opts)

        if pv2 in ('', None, 'None'):
            pv2 = None
        if form.get('submit', 'From Present').lower().startswith('from'):
            date1 = form.get('time_ago', '1_days')
            return plot(pv, pv2=pv2, timevar='time_ago', date1=date1,
                        pvmin=pvmin, pvmax=pvmax, pv2min=pv2min, pv2max=pv2max, fdat=fdat)
        else:
            date1 = form.get('date1', None)
            date2 = form.get('date2', None)
            return plot(pv, pv2=pv2, timevar='date_range', date1=date1, date2=date2,
                        pvmin=pvmin, pvmax=pvmax, pv2min=pv2min, pv2max=pv2max, fdat=fdat)

    return Response(" Create Plot based on Form Submission(Date Range) %s" %  form.items())
