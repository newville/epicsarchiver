#!/usr/bin/python
from mod_python import apache
from EpicsArchiver import WebAdmin, config


def is_valid(user,passwd):
    passdata = {config.dbuser: config.dbpass}
    return  (passdata.has_key(user) and passdata[user] == passwd)

__auth_realm__ = "Archiver password for '%s'!"  % config.dbuser

def __auth__(req,user,passwd):
    if is_valid(user,passwd): return 1
    return 0

def index(req,pv='',**kw):
    p = WebAdmin(**kw)
    return p.show_adminpage(pv=pv)


def pvinfo(req,pv=None,**kw):
    global arch
    try:
        arch is None
    except NameError:
        arch = None

    p = WebAdmin(arch=arch)
    arch = p.arch

    return p.show_pvinfo(pv,**kw)

def related_pvs(req,pv=None,**kw):
    global arch
    try:
        arch is None
    except NameError:
        arch = None

    p = WebAdmin(arch=arch)
    arch = p.arch

    return p.show_related_pvs(pv,**kw)


def instruments(req,station=None,instrument=None,pv=None,**kw):
    global arch
    try:
        arch is None
    except NameError:
        arch = None

    p = WebAdmin(arch=arch)
    arch = p.arch

    return p.show_instruments(station=station,instrument=instrument,pv=pv,**kw)

