#!/usr/bin/python
from mod_python import apache
from EpicsArchiver import WebInstruments

    
def dispatch(req,method,**kw):
    global arch
    try:
        arch is None
    except NameError:
        arch = None

    p = WebInstruments(arch=arch)
    arch = p.arch

    return getattr(p,method)(**kw)


def index(req,**kw):                return dispatch(req,'show',**kw)
def add_instrument(req,**kw):       return dispatch(req,'add_instrument',**kw)
def modify_instrument(req,**kw):    return dispatch(req,'modify_instrument',**kw)    
def manage_positions(req,**kw):     return dispatch(req,'manage_positions',**kw)    
def add_station(req,**kw):          return dispatch(req,'add_station',**kw)
def view_position(req,**kw):        return dispatch(req,'view_position',**kw)
