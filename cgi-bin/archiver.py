#!/usr/bin/python

from mod_python import apache
from EpicsArchiver.PlotViewer import PlotViewer

def index(req,pv=None,pv2=None,**kw):
    global cache
    global arch

    try:
        cache is None
    except NameError:
        cache = None

    try:
        arch is None
    except NameError:
        arch = None

    p = PlotViewer(cache=cache,arch=arch,**kw) 
    cache = p.cache
    arch  = p.arch

    return p.show_pv(pv,pv2)

