#!/usr/bin/env python

import sys
from flask import (Flask, request, session, redirect, url_for,
                   abort, render_template, flash, Response)

from werkzeug import secure_filename

from EpicsArchiver import config
from EpicsArchiver.SimpleDB import Connection
from WebStatus import WebStatus
from PlotViewer import  PlotViewer
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

@app.route('/')
def index():
    return redirect(url_for('show', page='General'))

@app.route('/show/<page>')
def show(page=None):
    # cache = session.get('user_cache', None)
    # dbconn = session.get('user_dbconn', None)

    p = WebStatus(cache=None, dbconn=dbconn)

    # session['user_cache'] = p.cache
    # session['user_dbconn'] = p.dbconn
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
@app.route('/plot/<pv>/<pv2>/<time_ago>')
@app.route('/plot/<pv>/<pv2>/<time_ago>/<date1>')
@app.route('/plot/<pv>/<pv2>/<time_ago>/<date1>/<date2>')
def plot(pv=None, pv2=None, time_ago=None, date1=None, date2=None):
    opts = {'pv': pv,
            'pv2': pv2,
            'time_ago': time_ago,
            'date1': date1, 'date2': date2}

    return render_template('plot.html', **opts)

@app.route('/formplot', methods=['GET', 'POST'])
def formplot():
    return Response(" Form Plot")


@app.route('/oplot/<pv>')
@app.route('/oplot/<pv>/<pv2>')
@app.route('/oplot/<pv>/<pv2>/<time_ago>')
@app.route('/oplot/<pv>/<pv2>/<time_ago>/<date1>')
@app.route('/oplot/<pv>/<pv2>/<time_ago>/<date1>/<date2>')
def oplot(pv=None, pv2=None, time_ago=None, date1=None, date2=None):
    p = PlotViewer()
    return Response(p.do_plot(pv=pv, pv2=pv2,
                              time_ago=time_ago,
                              date1=date1, date2=date2))


@app.route('/admin')
def admin():
    return Response('Stub for Admin Page')


