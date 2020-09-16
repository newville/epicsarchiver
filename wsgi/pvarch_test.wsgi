#!/usr/bin/env python
# test pvarch server
import os
import sys
from flask import Flask, redirect
import epicsarchiver

topurl = "https://millenia.cars.aps.anl.gov/pvarch"

thisdir, thisfile = os.path.split(__file__)
sys.path.insert(0, thisdir)
os.environ['PVARCH_CONFIG'] = os.path.join(thisdir, 'config.toml')

from webapp import app
app.template_folder = os.path.join(thisdir, 'templates')
app.static_folder = os.path.join(thisdir, 'static')
application = app
