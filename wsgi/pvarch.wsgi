#!/usr/bin/env python

import os
import sys
from flask import Flask, redirect
try:
    import epicsarchiver
except:
    path = os.environ.get("PATH_INFO", "")
    exdir = "https://millenia.cars.aps.anl.gov/pvarch"

thisdir, thisfile = os.path.split(__file__)

sys.path.insert(0, thisdir)

os.environ['PVARCH_CONFIG'] = os.path.join(thisdir, 'config.toml')

try:
    from webapp import app
    app.template_folder = os.path.join(thisdir, 'templates')
    app.static_folder = os.path.join(thisdir, 'static')
    application = app
except:
    app = application = Flask(__name__)

    @app.route('/')
    def index(*args, **kws):
        return redirect('https://millenia.cars.aps.anl.gov/pvarch')
