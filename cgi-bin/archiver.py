#!/usr/bin/python

from mod_python import apache
from EpicsArchiver.PlotViewer import PlotViewer

def index(req,pv=None,pv2=None,**kw):
    global arch
    try:
        arch is None
    except NameError:
        arch = None

    p = PlotViewer(arch=arch,**kw) 
    arch  = p.arch

    return p.show_pv(pv,pv2)

