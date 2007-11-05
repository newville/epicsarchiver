#!/usr/bin/env python


from mod_python import apache

from EpicsArchiver import WebStatus, Cache, config, ConnectionPool
import sys

file_base   = config.template_dir
sys.path.insert(0,file_base)

from pages import pagelist, filemap


global pool
pool = ConnectionPool(size=16)

def show_page(req,page=None,**kw):
    dbconn = pool.get()

    p = WebStatus(dbconn=dbconn)
    
    p.begin_page(page, pagelist, refresh=30)
    
    if page == None: page = pagelist[0]
    if page in pagelist:
        p.show_pvfile(filemap[page])
   
    p.end_page()
    pool.put(dbconn)

    return p.get_buffer()

def index(req):
    return show_page(req)
