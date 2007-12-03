#!/usr/bin/env python


from mod_python import apache

import sys
from EpicsArchiver import config, WebStatus, PlotViewer, WebHelp, WebInstruments, ConnectionPool

DEBUG = False
logfile = None
if DEBUG:
    logfile = open("%s/web_dbpool.log" % config.data_dir, 'a')
    

# here we create a "Globabl Pool" of DB Connections for this process:
# as the apache process accesses pages, it will create/return/re-use
# db connections from this pool with pool.get() and pool.put()

global pool
pool = ConnectionPool(size=8,out=logfile)

# add the location of the web template file to the path 
file_base   = config.template_dir
sys.path.insert(0,file_base)


# methods for public access, called with: http://.../show.py/plot?key=arg&key=arg, etc

def plot(req,pv=None,pv2=None,**kw):
    " plot viewer "
    try:
        dbconn = req.dbconn
    except AttributeError:
        dbconn = pool.get()
        req.dbconn = dbconn
        
    p   = PlotViewer(dbconn=dbconn,**kw) 
    out = p.show_pv(pv,pv2)
    # pool.put(dbconn)
    return out


def show_page(req,page=None,**kw):
    " status pages "
    try:
        dbconn = req.dbconn
    except AttributeError:
        dbconn = pool.get()
        req.dbconn = dbconn

    p = WebStatus(dbconn=dbconn)

    # here we import the list of pages for the web templates
    from pages import pagelist, filemap

    p.begin_page(page, pagelist, refresh=30)
    if page == None: page = pagelist[0]
    if page in pagelist:
        p.show_pvfile(filemap[page])
   
    p.end_page()
    # pool.put(dbconn)
    return p.get_buffer()

def help(req,**kw):
    p = WebHelp()
    return p.show(**kw)

#methods for instruments:
def __Inst(req,method='show',**kw):
    try:
        dbconn = req.dbconn
    except AttributeError:
        dbconn = pool.get()
        req.dbconn = dbconn

    p = WebInstruments(dbconn=dbconn)
    out = getattr(p,method)(**kw)
    # pool.put(dbconn)
    return out

def instrument(req,**kw):           return __Inst(req,'show',**kw)
def show_instrument(req,**kw):      return __Inst(req,'show',**kw)
def add_instrument(req,**kw):       return __Inst(req,'add_instrument',**kw)
def modify_instrument(req,**kw):    return __Inst(req,'modify_instrument',**kw)    
def manage_positions(req,**kw):     return __Inst(req,'manage_positions',**kw)    
def view_position(req,**kw):        return __Inst(req,'view_position',**kw)
def add_station(req,**kw):          return __Inst(req,'add_station',**kw)

# default function:
def index(req):  return show_page(req,page=None)
