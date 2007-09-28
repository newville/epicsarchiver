#!/usr/bin/env python


from mod_python import apache

from EpicsArchiver import StatusWrite, config
import sys

file_base   = config.template_dir
sys.path.insert(0,file_base)

from pages import pagelist, filemap

# pagelist, filemap = map_files(file_base)

gen_file    = "%s/general.txt" % file_base
idc_file    = "%s/idc_data.txt" % file_base
aps_file    = "%s/aps_data.txt" % file_base
bmh2o_file  = "%s/bm_water.txt" % file_base
idh2o_file  = "%s/id_water.txt" % file_base
bmmono_file = "%s/bm_mono.txt" % file_base
idmono_file = "%s/id_mono.txt" % file_base
 
# pagelist = filelist.keys()
# ('General', 'Storage Ring', 'ID Mono', 'ID Vacuum',
#          'ID Water', 'BM Mono', 'BM Vacuum', 'BM Water', 'ID C')

def show_page(req,page='__',**kw):
    stat = StatusWriter()

    stat.begin_page(page, pagelist, refresh=30)
    
    if page = '__': page = pagelist[0]
    if page in pagelist:
        stat.show_pvfile(filemap[page])
   
    stat.end_page()

    return stat.get_buffer()


def index(req):          return show_page(req)
