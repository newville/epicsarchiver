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

def index(req,pv=None,pv2=None,**kw):
    p = WebAdmin(**kw)
    return p.show_adminpage()


def show_pvinfo(req,pv=None,**kw):
    global master

    try:
        master is None
    except NameError:
        master = None

    p = WebAdmin(master=master)
    master= p.master

    return p.show_pvinfo(pv,**kw)

