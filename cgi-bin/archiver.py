#!/usr/bin/python

from mod_python import apache
from EpicsArchiver.PlotViewer import PlotViewer

def index(req,pv=None,pv2=None,**kw):
    p = PlotViewer(**kw)
    return p.show_pv(pv,pv2)

