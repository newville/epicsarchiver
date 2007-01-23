#!/usr/bin/env python

import epicsHTML
import pvcache

from mod_python import apache

# gse_ = apache.import_module('epicsHTML')
# gse_ = reload(epicsHTML)

# bmd_file   = "/corvette/home/epics/Web/bmd_status.txt"
# idc_file   = "/corvette/home/epics/Web/idc_status.txt"
# idd_file   = "/corvette/home/epics/Web/idd_status.txt"
## file_base  = '/home/newville/public_html/py'
file_base  = '/corvette/home/epics/Web'
idc_file   = "%s/idc_data.txt" % file_base
aps_file   = "%s/aps_data.txt" % file_base
bmh2o_file = "%s/bm_water.txt" % file_base
idh2o_file = "%s/id_water.txt" % file_base
bmmono_file = "%s/bm_mono.txt" % file_base
idmono_file = "%s/id_mono.txt" % file_base

def show_page(req,page='General',new_session=True,**kw):
    global DBSAVE

    status = ''
    eh = epicsHTML.epicsHTML()

    DBSAVE = eh.cursor

    eh.begin_page(page, refresh=10)
    if   page == 'Storage Ring':   eh.add_pvfile(aps_file)
    elif page == 'ID Vacuum':      eh.show_idvac()
    elif page == 'BM Vacuum':      eh.show_bmvac()

    elif page == 'ID Mono':        eh.add_pvfile(idmono_file)        
    elif page == 'BM Mono':        eh.add_pvfile(bmmono_file)        

    elif page == 'ID Water':       eh.add_pvfile(idh2o_file)        
    elif page == 'BM Water':       eh.add_pvfile(bmh2o_file)        
    elif page == 'ID C':           eh.add_pvfile(idc_file)

    else:                          eh.show_general()

    eh.end_page(msg=status)
    return eh.get_buffer()

def general(req,**kw):  return show_page(req, page='General')
def aps(req,**kw):      return show_page(req, page='Storage Ring')
def idmono(req,**kw):   return show_page(req, page='ID Mono')
def bmmono(req,**kw):   return show_page(req, page='BM Mono')
def idh2o(req,**kw):    return show_page(req, page='ID Water')
def bmh2o(req,**kw):    return show_page(req, page='BM Water')
def idvac(req,**kw):    return show_page(req, page='ID Vacuum')
def bmvac(req,**kw):    return show_page(req, page='BM Vacuum')
def new(req,**kw):      return show_page(req, page='General',new_session=True)

def index(req):
    return show_page(req)
