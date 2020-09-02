#!/usr/bin/env python

import os
import sys
import epicsarchiver

thisdir, thisfile = os.path.split(__file__)

sys.path.insert(0, thisdir)

os.environ['PVARCH_CONFIG'] = os.path.join(thisdir, 'config.toml')

from webapp import app

app.template_folder = os.path.join(thisdir, 'templates')
app.static_folder = os.path.join(thisdir, 'static')

application = app
