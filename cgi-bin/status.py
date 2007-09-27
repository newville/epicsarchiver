#!/usr/bin/env python

import epicsHTML
from mod_python import apache


file_base  = '/corvette/home/epics/Web'
gen_file    = "%s/general.txt" % file_base
idc_file    = "%s/idc_data.txt" % file_base
aps_file    = "%s/aps_data.txt" % file_base
bmh2o_file  = "%s/bm_water.txt" % file_base
idh2o_file  = "%s/id_water.txt" % file_base
bmmono_file = "%s/bm_mono.txt" % file_base
idmono_file = "%s/id_mono.txt" % file_base

def show_page(req,page='General',**kw):
    global DBSAVE
    eh = epicsHTML.epicsHTML()
    DBSAVE = eh.cursor

    eh.begin_page(page, refresh=30)
    
    if   'Storage Ring' == page:   eh.show_pvfile(aps_file)
    elif 'ID Vacuum' == page:      eh.show_idvac()
    elif 'BM Vacuum' == page:      eh.show_bmvac()

    elif 'ID Mono' == page:        eh.show_pvfile(idmono_file)        
    elif 'BM Mono' == page:        eh.show_pvfile(bmmono_file)        

    elif 'ID Water' == page:       eh.show_pvfile(idh2o_file)        
    elif 'BM Water' == page:       eh.show_pvfile(bmh2o_file)        
    elif 'ID C' == page:           eh.show_pvfile(idc_file)

    else:                          eh.show_pvfile(gen_file)

    eh.end_page()
    return eh.get_buffer()

def general(req,**kw):  return show_page(req, page='General')
def aps(req,**kw):      return show_page(req, page='Storage Ring')
def idmono(req,**kw):   return show_page(req, page='ID Mono')
def bmmono(req,**kw):   return show_page(req, page='BM Mono')
def idh2o(req,**kw):    return show_page(req, page='ID Water')
def bmh2o(req,**kw):    return show_page(req, page='BM Water')
def idvac(req,**kw):    return show_page(req, page='ID Vacuum')
def bmvac(req,**kw):    return show_page(req, page='BM Vacuum')

def index(req):          return show_page(req)
