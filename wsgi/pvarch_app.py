#!/usr/bin/env python

import sys
from flask import (Flask, request, session, redirect, url_for,
                   abort, render_template, flash, Response)

from werkzeug import secure_filename
from epics import PV

from EpicsArchiver import config
from EpicsArchiver.SimpleDB import Connection
from WebStatus import WebStatus
from PlotViewer import  PlotViewer

from archive import ArchiveMaster

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


@app.route('/')
def index():
    return redirect(url_for('show', page='General'))


@app.route('/help')
def help():
    return render_template('help.html')    

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
    # text = "Session: %s <br> %s" % (dir(dbconn), (dbconn.conn))
    
    return Response("Conn %s <br> %s" % (hex(id(dbconn)), p.get_buffer()))

@app.route('/plot/<pv>')
@app.route('/plot/<pv>/<pv2>')
@app.route('/plot/<pv>/<pv2>/<timevar>')
@app.route('/plot/<pv>/<pv2>/<timevar>/<date1>')
@app.route('/plot/<pv>/<pv2>/<timevar>/<date1>/<date2>')
def plot(pv=None, pv2=None, timevar=None, date1=None, date2=None):

    if pv2     in ('', None, 'None'): pv2 = None
    if timevar in ('', None, 'None'): timevar = 'time_ago'
    if date1   in ('', None, 'None'): date1 = '1_days'
    if date2   in ('', None, 'None'): date2 = None

    if timevar == 'time_ago':
        tval, tunit  = date1.split('_')
    else:
        tval, tunit = '1', None

    messages = []
    ts, dat, enums, ylabel, ylog = None, None, None, None, False
    try:
        related = arch.related_pvs(pv)
        pvinfo  = arch.get_pvinfo(pv)
        desc    = pvinfo['desc']
        dtype   = pvinfo['type']
        if dtype == 'enum':
            thispv = PV(pv)
            thispv.get()
            enums = thispv.enum_strs

        ylog    = pvinfo['graph_type'].startswith('log')
        ts, dat = arch.get_data(pv, with_current=True)
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
            ts2, dat2 = arch.get_data(pv2, with_current=True)
            y2label="%s\n[%s]" % (desc2, pv2)
        except:
            messages.append("data for '%s' not found" % pv2)

    fig = None
    if ts is not None:
        fig = make_plot(ts, dat, ylabel=ylabel, ## ylog=ylog,
                        enums=enums,
                        ts2=ts2, dat2=dat2, y2label=y2label, # y2log=y2log,
                        enums2=enums2,
                        time_unit=tunit, time_val=tval)

    if len(messages) > 0:
        messages = ', '.join(messages)
    else:
        messages = None

    opts = {'pv': pv, 'pv2': pv2, 'timevar': timevar, 'date1': date1,
            'date2': date2, 'messages': messages, 'figure' : fig,
            'related': related}

    return render_template('plot.html', **opts)

@app.route('/formplot', methods=['GET', 'POST'])
def formplot():
    return Response(" Form Plot")


@app.route('/admin')
def admin():
    return Response('Stub for Admin Page')


