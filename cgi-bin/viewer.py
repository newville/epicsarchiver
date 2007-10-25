#!/usr/bin/python

from mod_python import apache
from EpicsArchiver.PlotViewer import PlotViewer

def index(req,pv='',pv2='',**kw):
    global arch
    try:
        arch is None
    except NameError:
        arch = None

    p = PlotViewer(arch=arch) 
    arch  = p.arch

    return p.show_pv(pv,pv2,**kw)

