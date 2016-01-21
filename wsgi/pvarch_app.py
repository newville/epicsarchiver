#!/usr/bin/env python

import sys
from flask import (Flask, request, session, redirect, url_for,
                   abort, render_template, flash, Response)

from werkzeug import secure_filename

from EpicsArchiver import config, WebStatus, PlotViewer, WebHelp, WebInstruments

import sys
sys.path.insert(0, config.template_dir)

from pages import pagelist, filemap

app = Flask(__name__)
app.config.from_object(__name__)
app.debug = True

@app.route('/')
def index():
    return redirect(url_for('show', page='General'))

@app.route('/show/<page>')
def show(page=None):
    p = WebStatus()
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

@app.route('/plot/<pv>')
@app.route('/plot/<pv>/<pv2>')
@app.route('/plot/<pv>/<pv2>/<time_ago>')
@app.route('/plot/<pv>/<pv2>/<time_ago>/<date1>')
@app.route('/plot/<pv>/<pv2>/<time_ago>/<date1>/<date2>')
def plot(pv=None, pv2=None, time_ago=None, date1=None, date2=None):
    p = PlotViewer()
    return Response(p.do_plot(pv=pv, pv2=pv2,
                              time_ago=time_ago,
                              date1=date1, date2=date2))



