#!/usr/bin/python

from mod_python import apache
from EpicsArchiver.WebHelp import WebHelp

def index(req,**kw):
    p = WebHelp()
    return p.show(**kw)

