#!/usr/bin/python

from mod_python import apache
from EpicsArchiver import WebAdmin, config, ConnectionPool

DEBUG = False

logfile = None
if DEBUG:
    logfile = open("%s/webadmin_dbpool.log" % config.data_dir, 'a')

global pool
pool = ConnectionPool(size=8,out=logfile)

def is_valid(user,passwd):
    passdata = {config.dbuser: config.dbpass}
    return  (passdata.has_key(user) and passdata[user] == passwd)

__auth_realm__ = "Archiver password for '%s'!"  % config.dbuser

def __auth__(req,user,passwd):
    if is_valid(user,passwd): return 1
    return 0

def __Admin(method,**kw):
    dbconn1 = pool.get()
    dbconn2 = pool.get()
    p = WebAdmin(dbconn1=dbconn1,dbconn2=dbconn2)

    out = getattr(p,method)(**kw)

    pool.put(dbconn1)
    pool.put(dbconn2)
    return out

def index(req,**kw):        return __Admin('show_adminpage',**kw)
def pvinfo(req,**kw):       return __Admin('show_pvinfo',**kw)
def related_pvs(req,**kw):  return __Admin('show_related_pvs',**kw)    
def alerts(req,**kw):       return __Admin('show_alerts',**kw)
def list_alerts(req,**kw):  return __Admin('show_all_alerts',**kw)    
