#!/usr/bin/env python


from mod_python import apache

from EpicsArchiver import WebStatus, Cache, config
import sys

file_base   = config.template_dir
sys.path.insert(0,file_base)

from pages import pagelist, filemap

def show_page(req,page=None,**kw):
    global cache
    try:
        cache is None
    except NameError:
        cache = None

    stat   = WebStatus()
    cache  = stat.cache

    cache.db.get_cursor()
    stat.begin_page(page, pagelist, refresh=30)
    
    if page == None: page = pagelist[0]
    if page in pagelist:
        stat.show_pvfile(filemap[page])
   
    stat.end_page()

    cache.db.put_cursor()

    return stat.get_buffer()

def index(req):
    return show_page(req)
