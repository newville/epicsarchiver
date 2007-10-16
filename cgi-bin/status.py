#!/usr/bin/env python


from mod_python import apache

from EpicsArchiver import StatusWriter, Cache, ArchiveMaster, config
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

    stat   = StatusWriter(cache=cache)

    cache  = stat.cache

    stat.begin_page(page, pagelist, refresh=30)
    
    if page == None: page = pagelist[0]
    if page in pagelist:
        stat.show_pvfile(filemap[page])
   
    stat.end_page()
    return stat.get_buffer()

def index(req):
    return show_page(req)
