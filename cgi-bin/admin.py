#!/usr/bin/python
from mod_python import apache
from EpicsArchiver import WebAdmin, config


def is_valid(user,passwd):
    passdata = {config.dbuser: config.dbpass}
    return  (passdata.has_key(user) and passdata[user] == passwd)

__auth_realm__ = "Archiver password for '%s'!"  % config.dbuser

def __auth__(req,user,passwd):
    if is_valid(user,passwd): return 1
    return 0



def dispatch(req,method,**kw):
    global arch
    try:
        arch is None
    except NameError:
        arch = None

    p = WebAdmin(arch=arch)
    arch = p.arch

    return getattr(p,method)(**kw)

def index(req,**kw):        return dispatch(req,'show_adminpage',**kw)
def pvinfo(req,**kw):       return dispatch(req,'show_pvinfo',**kw)
def related_pvs(req,**kw):  return dispatch(req,'show_related_pvs',**kw)    
def alerts(req,**kw):       return dispatch(req,'show_alerts',**kw)
def list_alerts(req,**kw):  return dispatch(req,'show_all_alerts',**kw)    

