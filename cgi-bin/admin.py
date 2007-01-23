#!/usr/bin/python
from mod_python import apache
import PV_Viewer
import sha
## x_ = apache.import_module('PV_Viewer')
    
def get_passwords():
    secure  = '/www/apache/security/pvarchive.txt'
    f = open(secure)
    data = {}
    for line in f.readlines():
        line = line.strip()
        if line.startswith('#') or len(line)<1: continue
        u = line.split(':')
        if len(u)<2: continue
        user,pwd = u[0],u[1]
        data[user] = pwd
    return data

def is_valid(user,passwd):
    passdata = get_passwords()    
    if passdata.has_key(user):
        s = sha.new()
        s.update(passwd)
        test = s.hexdigest()
        if passdata[user] == test: return True
    return False

__auth_realm__ = "epics / guest password!" 

def __auth__(req,user,passwd):
    if is_valid(user,passwd): return 1
    return 0

def index(req,pv=None,pv2=None,**kw):
    p = PV_Viewer.PV_Admin(**kw)
    return p.show_adminpage()


def show_pvinfo(req,pv=None,**kw):
    p = PV_Viewer.PV_Admin()
    return p.show_pvinfo(pv,**kw)

