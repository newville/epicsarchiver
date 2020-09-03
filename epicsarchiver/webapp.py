#!/usr/bin/env python
import os
import sys
import toml
import json
from flask import (Flask, request, session, redirect, url_for,
                   abort, render_template, flash, Response)

from time import time, mktime, strftime, localtime
from datetime import datetime

import numpy as np

from epicsarchiver import get_config, Archiver, tformat
from epicsarchiver.web_utils import (parse_times, chararray_as_string,
                                     auto_ylog, make_plot)

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

ago_choices = ['1 day', '1 week', '4 weeks', '12 weeks', '1 year']


def session_init(session, force_refresh=False):
    global pvarch_config, archiver, cache
    global cache_data, enum_strings
    global last_refresh, age
    if archiver is None:
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

    if dat.dtype.type == np.string:
        dat = chararray_as_string(dat)
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





@app.route('/plot/<date1>')
@app.route('/plot/<date1>/<date2>')
@app.route('/plot/<date1>/<date2>/<pv1>')
@app.route('/plot/<date1>/<date2>/<pv1>/<pv2>')
@app.route('/plot/<date1>/<date2>/<pv1>/<pv2>/<pv3>')
@app.route('/plot/<date1>/<date2>/<pv1>/<pv2>/<pv3>/<pv4>')
@app.route('/plot/<date1>/<date2>/<pv1>/<pv2>/<pv3>/<pv4>/<pv5>')
@app.route('/plot/<date1>/')
@app.route('/plot/<date1>/<date2>/')
@app.route('/plot/<date1>/<date2>/<pv1>/')
@app.route('/plot/<date1>/<date2>/<pv1>/<pv2>/')
@app.route('/plot/<date1>/<date2>/<pv1>/<pv2>/<pv3>/')
@app.route('/plot/<date1>/<date2>/<pv1>/<pv2>/<pv3>/<pv4>/')
@app.route('/plot/<date1>/<date2>/<pv1>/<pv2>/<pv3>/<pv4>/<pv5>/')
def plot(date1='1week', date2=None, pv1=None, pv2=None, pv3=None, pv4=None, pv5=None):
    """plot with plain link, only command line args: see also formplot()
    """
    session_init(session)
    if pv1 is None:
        if date2 is None:
            pv1 = date1
            date1 = '1week'
            date2 = 'none'
        else:
            pv1 = date2
            date2 = 'none'

    if date1 is None: date1 = 'none'
    if date2 is None: date2 = 'none'

    if date1 == 'none' or len(date1) < 2:
        date1 = '1week'
    if date2 == 'none' or len(date2) < 2:
        date2 = 'none'

    date1, date2 = parse_times(date1, date2)
    tmin = date1.timestamp()
    tmax = date2.timestamp()

    print("Plot: ",  tmin, tmax, date1, date2, pv1)

    fig = ''
    pvdata = []
    related = []
    if pv1 is not None:
        related = cache.get_related(pv1, limit=20)

    for pv in (pv1, pv2, pv3, pv4, pv5):
        if pv in ('', 'None', None):
            continue
        pvinfo = archiver.get_pvinfo(pv)
        label  = "%s [%s]" % (pvinfo['description'], pv)
        dtype  = pvinfo['type'].lower()
        enums  = enum_strings.get(pv, ['Unknown'])

        ylog   = pvinfo['graph_type'].startswith('log')
        t, y   = archiver.get_data(pv, tmin=tmin, tmax=tmax, with_current=True)

        if dtype == 'string':
            y = [chararray_as_string(i) for i in y]

        current_t = t.pop()
        current_y = y.pop()
        pvdata.append((pv, t, y, label, ylog, dtype, enums, current_t, current_y))
    if len(pvdata) > 0:
        fig = make_plot(pvdata)

    return render_template('plot.html',
                           related=related, time_ago=ago_choices[2],
                           ago_choices=ago_choices,
                           config=pvarch_config, fig=fig,
                           last_refresh=last_refresh, age=age,
                           cache_data=cache_data,
                           enum_strings=enum_strings)


@app.route('/formplot', methods=['GET', 'POST'])
def formplot():
    session_init(session)
    print("Form Plot ", request.form)

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
