#!/usr/bin/env python
import os
import sys

import toml

from flask import (Flask, request, session, redirect, url_for,
                   abort, render_template, flash, Response)

from time import time, mktime, strftime
from datetime import datetime, timedelta
from dateutil.parser import parse as dateparser
import numpy as np


from epicsarchiver import get_config, Archiver, tformat


# sys.path.insert(0, config.template_dir)

# note: this expects that the environmental variable
# will be set and accessible by the web server, and we
# need config at the top-level to set the application secret key.

pvarch_config = get_config().asdict()
web_dirs = [pvarch_config.get('web_url', '.')]
if '.' not in web_dirs:
    web_dirs.append('.')

for dirname in web_dirs:
    conf_file = os.path.abspath(os.path.join(dirname, 'config.toml'))
    if os.path.exists(conf_file):
        pvarch_config.update(toml.load(open(conf_file)))

app = Flask(__name__)
app.config.from_object(__name__)
app.secret_key = pvarch_config['web_secret_key']

archiver = cache = None
last_refresh = age = 0
cache_data = {}
enum_strings = {}

ago_choices = {'1 hour': 1, '8 hour': 8, '1 day': 24,
               '4 days': 96, '1 week': 168, '4 weeks': 672,
               '12 weeks': 2016, '1 year': 8736}



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
        now = time.time()
        dt1 = datetime.fromtimestamp(now - 3600*factor*date1)
        dt2 = datetime.fromtimestamp(now)
    else: # provided start/stop times
        dt1 = dateparser(date1)
        dt2 = dateparser(date2)
    return (dt1, dt2)


def convert_string_data(val):
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


def session_init(session, force_refresh=False):
    global pvarch_config, archiver, cache
    global cache_data, enum_strings
    global last_refresh, age
    if archiver is None:
        print("initializer archiver: ", pvarch_config)
        archiver = Archiver(**pvarch_config)
        cache = archiver.cache

    now = time()
    age = now - last_refresh
    if len(cache_data) < 1 or age > 3600:
        cache_data = cache.get_values_dict(all=True)
        enum_strings = cache.get_enum_strings()

    else:
        cache_data.update(cache.get_values_dict(time_ago=(5 + 2*age)))
    last_refresh = now

def toNone(val):
    if val in ('', 'None', None):
        val = None
    return val

@app.route('/')
def index():
    session_init(session)
    return render_template('show_config.html',
                           config=pvarch_config,
                           last_refresh=last_refresh, age=age,
                           cache_data=cache_data, enum_strings=enum_strings)

@app.route('/status')
def status():
    session_init(session)
    return render_template('status.html',
                           status=archiver.status_report(),
                           admin=session['is_admin'])


@app.route('/pagex')
def pagex():
    session_init(session)
    return render_template('page1.html',
                           config=pvarch_config,
                           last_refresh=last_refresh, age=age,
                           cache_data=cache_data, enum_strings=enum_strings)



@app.route('/help')
def help():
    config.pvdat1 = config.dat_format % (config.dat_prefix, 1)
    config.pvdat2 = config.dat_format % (config.dat_prefix, 2)
    config.pvdat128 = config.dat_format % (config.dat_prefix, 128)
    return render_template('help.html', version=__version__, config=config)


@app.route('/alerts')
def alerts():
    session_init(session)
    return render_template('alerts.html',
                           alerts=cache.get_alerts(),
                           admin=session['is_admin'],
                           alert_choices=alert_ops)


@app.route('/editalert/<int:alertid>')
def editalert(alertid=None):
    session_init(session)
    alerts = cache.get_alerts()
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

        alerts = cache.get_alerts()
        for a in alerts:
            if a.id == alertid:
                thisalert = a

        print(" ALERT ", alertid, name, pvname, compare)


        if makecopy:
            cache.add_alert(pvname=pvname, name="%s (copy)" % name,
                            mailto=mailto, mailmsg=mailmsg, timeout=timeout,
                            compare=compare, trippoint=trippoint)
        else:
            cache.update_alert(alertid=alertid, pvname=pvname, name=name,
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
    # admin = session['is_admin']

    if date1 is not None and date1.endswith('.dat'):
        date1 = None
    if date2 is not None and date2.endswith('.dat'):
        date2 = None

    tmin, tmax, date1, date2, time_ago = parse_times(timevar, date1, date2)
    ts, dat = archiver.get_data(pv, tmin=tmin, tmax=tmax, with_current=True)

    print("Got Data ",  tmin, tmax, time_ago, len(ts), len(dat))

    stmin = strftime("%Y-%m-%d %H:%M:%S", localtime(tmin))
    stmax = strftime("%Y-%m-%d %H:%M:%S", localtime(tmax))

    pvinfo  = archiver.get_pvinfo(pv)

    buff = ['# Data for %s [%s] '      % (pv, pvinfo['desc']),
            '# Time Range: %s , %s'   % (stmin, stmax),
            '# Timestamps: [%.1f : %.1f]' % (tmin, tmax),
            '# Data Type: %s'           % pvinfo['type']]

    fmt = '%13.7g'
    if pvinfo['type'] == 'enum':
        buff.append('# Value Meanings:')
        for _i, _enum in enumerate(enum_strings.get(pv, ['Unknown'])):
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

@app.route('/plot/<date1>/<date2>/<pv1>')
@app.route('/plot/<date1>/<date2>/<pv1>/<pv2>')
@app.route('/plot/<date1>/<date2>/<pv1>/<pv2>/<pv3>')
@app.route('/plot/<date1>/<date2>/<pv1>/<pv2>/<pv3>/<pv4>')
@app.route('/plot/<date1>/<date2>/<pv1>/<pv2>/<pv3>/<pv4>/<pv5>')
def plot(date1='day', date2='none', pv1=None, pv2=None,
         pv3=None, pv4=None, pv5=None):

    session_init(session)

    date1, date2 = parse_times(date1, date2)
    tmin = date1.timestamp()
    tmax = date2.timestamp()

    print("Plot: ",  tmin, tmax, time_ago)

    pvdata = []
    related = []
    if pv1 is not None:
        related = cache.get_related(pv, limit=20)

    for pv in (pv1, pv2, pv3, pv4, pv5):
        pvinfo = archiver.get_pvinfo(pv)
        label  = "%s [%s]" % (pvinfo['description'], pv)
        dtype  = pvinfo['type'].lower()
        enums  = enum_strings.get(pv, ['Unknown'])

        ylog   = pvinfo['graph_type'].startswith('log')
        t, y   = archiver.get_data(pv, tmin=tmin, tmax=tmax, with_current=True)
        if dtype == 'string':
            y = [convert_string_data(i) for i in y]
        pvdata.append((t, y, label, ylog, dtype, enums))

    if len(pvdata) == 1 and pvdata[0][4] == 'string':


    fig, pvdata, pv2data = None, None, None
    print(" getting data ")
    if ts is not None:
        current_ts = ts.pop()
        current_val =  dat.pop()

        fig = make_plot(ts, dat, ylabel=ylabel,
                        enums=enums,  ylog=ylog,
                        ts2=ts2, dat2=dat2, y2label=y2label,
                        enums2=enums2, y2log=y2log,
                        tmin=tmin, tmax=tmax,
                        ymin=pvmin, ymax=pvmax,
                        y2min=pv2min, y2max=pv2max)

    opts = {'pv': pv,
            'fig' : fig,
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
            'related': related,
            'ago_choices':  ago_choices}


    return render_template('plot.html',
                           config=pvarch_config,
                           last_refresh=last_refresh, age=age,
                           cache_data=cache_data,
                           enum_strings=enum_strings,
                           **opts)


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
