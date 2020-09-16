#!/usr/bin/env python

import os
import sys
from flask import Flask, redirect

import epicsarchiver

thisdir, thisfile = os.path.split(__file__)
sys.path.insert(0, thisdir)
os.environ['PVARCH_CONFIG'] = os.path.join(thisdir, 'config.toml')

config = epicsarchiver.get_config().asdict()
try:
    from epicsarchiver.webapp import app
    app.template_folder = os.path.join(thisdir, 'templates')
    app.static_folder = os.path.join(thisdir, 'static')
    application = app
except:
    app = application = Flask(__name__)
    @app.route('/')
    def index(*args, **kws):
        return redirect("{web_baseurl:s}/{web_url:s}".format(**config))
