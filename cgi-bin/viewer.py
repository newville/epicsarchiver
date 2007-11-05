#!/usr/bin/python

from mod_python import apache
from EpicsArchiver import PlotViewer, ConnectionPool

 
global pool
pool = ConnectionPool(size=16)
 
def index(req,pv=None,pv2=None,**kw):
    dbconn = pool.get()
    p = PlotViewer(dbconn=dbconn,**kw)
    out = p.show_pv(pv,pv2)
    pool.put(dbconn)
    return out

