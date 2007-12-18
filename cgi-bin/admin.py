#!/usr/bin/python

from mod_python import apache
from EpicsArchiver import WebAdmin, config, ConnectionPool

__auth_realm__ = "Archiver password for '%s'!"  % config.dbuser

def __auth__(req,user='',passwd=''):
    if user == config.dbuser and passwd == config.dbpass: return 1
    return 0

def __Admin(req,method,**kw):
    try:
        dbconn = req.dbconn
    except AttributeError:
        dbconn = None
        req.dbconn = dbconn

    p = WebAdmin(dbconn=dbconn)
    req.dbconn = p.dbconn

    out = getattr(p,method)(**kw)
    return out

def index(req,**kw):        return __Admin(req,'show_adminpage',**kw)
def pvinfo(req,**kw):       return __Admin(req,'show_pvinfo',**kw)
def related_pvs(req,**kw):  return __Admin(req,'show_related_pvs',**kw)    
def alerts(req,**kw):       return __Admin(req,'show_alerts',**kw)
def list_alerts(req,**kw):  return __Admin(req,'show_all_alerts',**kw)    
