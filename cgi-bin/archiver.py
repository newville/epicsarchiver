#!/usr/bin/python
from mod_python import apache
import PV_Viewer

# x_ = apache.import_module('PV_Viewer')
# gse_ = reload(PV_Viewer)

def index(req,pv=None,pv2=None,**kw):
    p = PV_Viewer.PV_Viewer(**kw)
    return p.show_pv(pv,pv2)

