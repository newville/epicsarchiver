#!/usr/bin/env python
import os
import sys
import toml
import json
from flask import (Flask, request, session, redirect, url_for,
                   abort, render_template, flash, Response, jsonify)

from time import time, ctime, strftime, localtime
from datetime import datetime

import numpy as np

from epicsarchiver import Archiver
from epicsarchiver.util import get_config, tformat, hformat, clean_string

from epicsarchiver.web_utils import (parse_times, chararray_as_string, ts2iso,
                                     auto_ylog, make_plot, PlotData, isnull,
                                     null2blank, cull_data)

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

ago_choices = ['15 minutes', '30 minutes', '1 hour',
               '4 hours', '12 hours',
               '1 day', '3 days', '1 week', '3 weeks',
               '6 weeks', '12 weeks', '26 weeks', '1 year']

cull_message = """Warning: data for %s culled for plotting (%d to %d values)"""

def update_data(session, force_refresh=False):
    global pvarch_config, archiver, cache
    global cache_data, enum_strings
    global last_refresh, age
    if archiver is None:
        archiver = Archiver(**pvarch_config)
        cache = archiver.cache
    if 'current_page' not in  pvarch_config:
        pvarch_config['current_page'] = 'Main Page'
    now = time()
    age = now - last_refresh
    if len(cache_data) < 1 or age > 3600:
        cache_data = cache.get_values_dict(all=True)
        enum_strings = cache.get_enum_strings()

    else:
        cache_data.update(cache.get_values_dict(time_ago=(5 + 2*age)))
    last_refresh = now
    cache_data.update({'pvarch_timestamp': {'id': 0, 'ts': now,
                                            'value': ctime(now),
                                            'cvalue': ctime(now),
                                            'dtype': 'string'}})
    if session.get('is_admin', None) is None:
        session['is_admin'] = False



@app.route('/')
def index():
    update_data(session)
    indexpage = pvarch_config.get('web_index', 'about')
    if not indexpage.endswith('.html'):
        indexpage = '%s.html' % indexpage
    return render_template(indexpage,
                           config=pvarch_config,
                           last_refresh=last_refresh, age=age,
                           cache_data=cache_data, enum_strings=enum_strings)


@app.route('/show/<page>')
def show(page=None):
    """
    Could be translated to static pages ?
    """
    update_data(session)
    # admin = session['is_admin']
    if page is None:
        page='Overview'
    pagename = "%s.html" % page
    return render_template(pagename,
                           config=pvarch_config,
                           last_refresh=last_refresh, age=age,
                           cache_data=cache_data, enum_strings=enum_strings)


@app.route('/rawdata')
def rawdata():
    """fetch data for javascript update"""
    update_data(session)
    data = {0: ctime()}
    for val in cache.get_values_dict(time_ago=30).values():
        data[val['id']] = val['cvalue']
    return jsonify(data)


@app.route('/status')
def status():
    update_data(session)
    cinfo = cache.get_info('cache')
    ainfo = cache.get_info('archive')
    return render_template('status.html',
                           config=pvarch_config,
                           etime=60,
                           cache_db=cinfo.db,
                           cache_status=cinfo.status,
                           cache_nnew=len(cache.get_values(time_ago=60)),
                           arch_db=ainfo.db,
                           arch_status=ainfo.status,
                           arch_nnew=cache.get_narchived(time_ago=60),
                           last_refresh=last_refresh, age=age,
                           cache_data=cache_data, enum_strings=enum_strings)


@app.route('/help')
def help():
    return render_template('help.html', version='2.1',
                           config=pvarch_config)


@app.route('/alerts')
def alerts():
    update_data(session)
    alerts = []
    ops = {'ne': '!=', 'eq': '==', 'lt': '<', 'le': '<=',
           'gt': '>', 'ge': '>='}
    for pvname, dat in cache.get_alerts().items():

        tpoint = "%s %s" % (ops[clean_string(dat['compare'])],
                            clean_string(dat['trippoint']))
        alerts.append({'pvname': pvname, 'id': dat['id'],
                       'name': dat['name'],
                       'active': dat['active'],
                       'status': dat['status'],
                       'trip_point': tpoint})
    return render_template('alerts.html',
                           config=pvarch_config,
                           alerts=alerts)
#                    admin=session['is_admin'],
#alert_choices=alert_ops)


@app.route('/editalert/<int:alertid>')
def editalert(alertid=None):
    update_data(session)
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
    update_data(session)

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
    update_data(session)
    return render_template('admin.html',
                           admin=session['is_admin'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    update_data(session)
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
    update_data(session)
    session['is_admin'] = False
    return redirect(url_for('show', page='General'))



@app.route('/data/<date1>/<date2>/<pv>/<fname>')
def data(date1=None, date2=None, pv=None, fname=None):
    update_data(session)
    # admin = session['is_admin']

    dt1, dt2 = parse_times(date1, date2)
    tmin = dt1.timestamp()
    tmax = dt2.timestamp()
    pv = null2blank(pv)
    with_current = abs(time() - dt2.timestamp()) < 86400.0
    t, y =  archiver.get_data(pv, with_current=with_current,
                              tmin=tmin, tmax=tmax)

    pvinfo  = archiver.get_pvinfo(pv)
    pvinfo.update(dict(stmin=tformat(tmin), stmax=tformat(tmax),
                       now=tformat(time()), npts=len(y)))
    buff = ['''# Data for {name:s}
# Description: {description:s}
# Start Time:  {stmin:s}
# Stop Time:   {stmax:s}
# Data Type:   {type:s}
# Data Length: {npts:d}
# Extracted:   {now:s}'''.format(**pvinfo)]

    dtype = pvinfo['type']
    if dtype == 'enum':
        buff.append('# Meanings for Enum Values:')
        for _i, _enum in enumerate(enum_strings.get(pv, ['Unknown'])):
            buff.append('#   %i: %s' % (_i, _enum))

    # if dat.dtype.type == np.string:
    #    dat = chararray_as_string(dat)
    #    fmt = '%s'

    buff.append('#-------------------------------------------------')
    buff.append('# TimeStamp         Value    YYYYMMDD  HHMMSS')
    for _t, _v in zip(t, y):
        val = repr(_v)
        if dtype in ('int', 'enum'):
            val = "%d" %  _v
        elif dtype == 'double':
            val = hformat(_v)

        buff.append(' %.3f  %s  %s  %s' % (_t, val,
                                           strftime("%Y%m%d", localtime(_t)),
                                           strftime("%H%M%S", localtime(_t))))
    return Response("\n".join(buff), mimetype='text/plain')


@app.route('/plot/<date1>/')
@app.route('/plot/<date1>/<date2>/<pv1>/')
@app.route('/plot/<date1>/<date2>/<pv1>/<pv2>/')
@app.route('/plot/<date1>/<date2>/<pv1>/<pv2>/<pv3>/')
@app.route('/plot/<date1>/<date2>/<pv1>/<pv2>/<pv3>/<pv4>/')
def plot(date1, date2=None, pv1='', pv2='', pv3='', pv4='', time_ago=None):
    """plot with plain link, only command line args: see also formplot()
    """
    update_data(session)
    if time_ago is None:
        time_ago = '3 days'
    if date2 is None and len(pv1) < 1: # just passed pvname as only argument: plot/pvname
        pv1 = date1
        date2 = ts2iso(time())
        date1 = ts2iso(time() - 3*86400)

    dt1, dt2 = parse_times(date1, date2)

    now = time()
    with_current = abs(now - dt2.timestamp()) < 86400.0

    pv1 = null2blank(pv1)
    pv2 = null2blank(pv2)
    pv3 = null2blank(pv3)
    pv4 = null2blank(pv4)

    fig = table = tablepv = None
    messages = []
    plotdata = []
    related = []
    selected_pvs=[]
    for pv in (pv1, pv2, pv3, pv4):
        if isnull(pv):
            continue
        this = cache_data.get(pv, None)
        if this is None:
            continue
        selected_pvs.append(pv)
        try:
            pvid = cache_data.get(pv, {id:-1})['id']
        except:
            print("Could not get cache data ", pv, cache_data.get(pv, {id:-1}))
            continue
        related.append((pv, pvid))
        pvinfo = archiver.get_pvinfo(pv)
        label  = "%s [%s]" % (pvinfo['description'], pv)
        label  = pvinfo['description']
        dtype  = pvinfo['type'].lower()
        if dtype == 'enum':
            enum_labels = enum_strings.get(pv, ['Unknown'])
        else:
            enum_labels = None

        force_ylog   = pvinfo['graph_type'].startswith('log')
        t, y =  archiver.get_data(pv, with_current=with_current,
                                  tmin=dt1.timestamp(),
                                  tmax=dt2.timestamp())
        if dtype == 'string' and table is None: # only show table of 1st string PV
            table = []
            tablepv = pv
            for _t, _y in  zip(t, y):
                table.append((ts2iso(_t), chararray_as_string(_y)))
        else:
            npts_total = len(t)
            if npts_total > 30000:
                while len(t) > 30000:
                    t, y = cull_data(t, y, sample=3, percent=15)
                t, y = t.tolist(), y.tolist()
                messages.append(cull_message % (pv, npts_total, len(t)))

            thisplot = PlotData(t=t, y=y, pvname=pv, label=label,
                                force_ylog=force_ylog,
                                enum_labels=enum_labels)

            plotdata.append(thisplot)

    if len(plotdata) > 0:
        fig = make_plot(plotdata)

    if len(plotdata) > 1:
        tmp = [p.pvname for p in plotdata]
        nvars = len(tmp)
        print("INCRE PAAIR SCORES for ", tmp)
        for i in range(nvars):
            pni = tmp[i]
            for j in range(i+1, nvars):
                cache.increment_pair_score(pni, tmp[j])

    # now fix related to be list of (pvname, pvid) and so that we have the top 3
    # scores for each PV and then order by total scores, up to 20:
    related_work = {}
    for apv in selected_pvs:
        rel = list(cache.get_related(apv, limit=20).items())
        for i in range(min(len(rel), 5)):
            pvname, score = rel.pop(0)
            try:
                pvid = cache_data.get(pvname, {id:-1})['id']
            except:
                print("Could not get cache data ", pvname, cache_data.get(pvname, {id:-1}))
                continue
            if (pvname, pvid) not in related:
                related.append((pvname, pvid))
        for pvname, score in rel:
            if pvname in related_work:
                related_work[pvname] += score
            else:
                related_work[pvname] = score

    for oname, score in sorted(related_work.items(), key=lambda a: -a[1]):
        try:
            other = cache_data[oname]['id']
        except:
            pvid  = -1
        if other>-1 and (oname, other) not in related:
            related.append((oname, other))

    return render_template('plot.html', messages=messages, nmessages=len(messages),
                           pv1=pv1, pv2=pv2, pv3=pv3, pv4=pv4,
                           date1=dt1.isoformat().replace('T', ' '),
                           date2=dt2.isoformat().replace('T', ' '),
                           selected_pvs=selected_pvs,
                           related=related,
                           time_ago=time_ago,
                           ago_choices=ago_choices,
                           config=pvarch_config,
                           fig=fig, table=table, tablepv=tablepv,
                           last_refresh=last_refresh,
                           age=age,
                           cache_data=cache_data,
                           enum_strings=enum_strings)


@app.route('/formplot', methods=['GET', 'POST'])
def formplot():
    if request.method != 'POST':
        return Response(" Create Plot based on Form Submission(Date Range) %s" %  form.items())

    update_data(session)
    form = request.form
    date1  = form.get('date1', '3 days')
    date2  = form.get('date2', 'now')

    submit = form.get('submit', 'Time From Present').lower()

    if 'plot selected' in submit:
        pvs = dict(pv1=None, pv2=None, pv3=None, pv4=None)
        i = 0
        pv1 = pv2 = pv3 = pv4 = None
        for key, val in form.items():
            if key.startswith('sel_'):
                pvid = int(key[4:])
                for pvname, pvdata in cache_data.items():
                    if int(pvdata['id']) == int(pvid):
                        i = i+1
                        pvs['pv%d' % i] = pvname
                        break
                if i == 4:
                    break
    else:
        pvs = dict(pv1=null2blank(form.get('pv1', '')),
                   pv2=null2blank(form.get('pv2', '')),
                   pv3=null2blank(form.get('pv3', '')),
                   pv4=null2blank(form.get('pv4', '')))
        if 'from' in submit:
            pvs['time_ago'] = date1 = form.get('time_ago', '3 days')
            date2 = 'now'
    return plot(date1=date1, date2=date2, **pvs)
