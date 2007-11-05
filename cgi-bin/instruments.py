#!/usr/bin/python
from mod_python import apache
from EpicsArchiver import WebInstruments, ConnectionPool

global pool
pool = ConnectionPool(size=8)
   
def dispatch(req,method,**kw):
    if method is None: return index(req)

    dbconn = pool.get()
    p = WebInstruments(dbconn=dbconn)

    out = getattr(p,method)(**kw)
    pool.put(dbconn)
    return out

def index(req,**kw):                return dispatch(req,'show',**kw)
def add_instrument(req,**kw):       return dispatch(req,'add_instrument',**kw)
def modify_instrument(req,**kw):    return dispatch(req,'modify_instrument',**kw)    
def manage_positions(req,**kw):     return dispatch(req,'manage_positions',**kw)    
def add_station(req,**kw):          return dispatch(req,'add_station',**kw)
def view_position(req,**kw):        return dispatch(req,'view_position',**kw)
