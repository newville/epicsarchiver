#!/usr/bin/env python
#
import time
from MySQLdb import string_literal, escape_string

MAX_EPOCH = 2147483647.0   # =  2**31 - 1.0 (max unix timestamp)
SEC_DAY   = 86400.0

motor_fields = ('.VAL','.OFF','.FOFF','.SET','.HLS','.LLS','.DIR','_able.VAL','.SPMG','.DESC')

valid_pvstr = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:._'

def clean_input(x,maxlen=256):
    """clean input, forcing it to be a string, with comments stripped,
    and guarding against extra sql statements"""
    if not isinstance(x,(unicode,str)): x = str(x)

    if len(x)>maxlen:   x = x[:maxlen-1]
    x.replace('#','\#')
    
    eol = x.find(';')
    if eol > -1: x = x[:eol]
    return x.strip()
                       
def safe_string(x):
    x = clean_input(x)
    if "'" in x:  return  '"%s"' %  escape_string(x)
    return  string_literal(x)

def clean_string(x):
    x = clean_input(x)
    if "'" in x:  return  '"%s"' %  escape_string(x)
    return  string_literal(x)

def normalize_pvname(p):
    """ normalizes a PV name (so that it ends in .VAL if needed)."""
    x = clean_input(p.strip())
    if len(x) > 2 and x.find('.') < 1: return '%s.VAL' % x
    return x

def get_force_update_time():
    """ inserts will be forced into the Archives for stale values
    between 18 and 21 hours after last insert.
    This will spread out inserts, and means that every PV is
    recorded at least once in any 24 hour period.  
    """
    from random import random
    return 10800.0*(6 + random())

def timehash():
    """ genearte a simple, 10 character hash of the timestamp:
    Number of possibilites = 16^10 ~= 10^12,
    the hash is a linear-in-milliseconds timestamp, so collisions
    cannot happen for 10^12 milliseconds (33 years). """ 
    return hex(int(1000*time.time()))[-10:]

def tformat(t=None,format="%Y-%m-%d %H:%M:%S"):
    """ time formatting"""
    if t is None: t = time.time()
    return time.strftime(format, time.localtime(t))

def time_str2sec(s):
    xdate,xtime = s.split(' ')
    hr,min,sec  = xtime.split(':')
    yr,mon,day  = xdate.split('-')
    dx = time.localtime()
    return time.mktime((int(yr),int(mon),int(day),int(hr),int(min), 0,0,0,dx[8]))


def valid_pvname(pvname):
    for c in pvname:
        if c not in valid_pvstr: return False
    return True
    
def set_pair_scores(pvlist):
    """ set (or check) that all pairs of pvs in list pvlist have a 'pair score'"""
    if not isinstance(pvlist,(list,tuple)): return
    if len(pvlist)< 2: return
    from MasterDB import MasterDB

    m = MasterDB()
    get_score = m.get_pair_score
    set_score = m.set_pair_score
       
    while pvlist:
        q = pvlist.pop()
        for p in pvlist:
            if get_score(q,p)<1: set_score(q,p,10)
            
    m.close()
    m = None
    return 

def get_related_pvs(pvname):
    m = MasterDB()
    out = m.get_related_pvs(normalize_pvname(pvname),minscore=1)
    m.close()
    m = None
    return out

def increment_pair_score(pv1,pv2):
    from MasterDB import MasterDB
    m = MasterDB()
    m.increment_pair_score(normalize_pvname(pv1),normalize_pvname(pv2))
    m.close()
    m = None

def write_saverestore(pvvals,format='plain',header=None):
    """ generate a save/restore file for a set of PV values

    pvvals is a list or tuple of (pvname,value) pairs
    format can be
        plain   plain save/restore file
        idl     idl script
        python  python script       
    header: list of additional header/comment lines
    """
    out = []
    fmt = format.lower()

    xfmt = "%s  %s"
    cmt  = '#'
    if format.startswith('idl'):
        out.append("; IDL save restore script")
        xfmt = "s = caput('%s', %s)"
        cmt  = ';'
    elif format.startswith('py'):
        out.append("#!/usr/bin/env python")
        out.append("#  Python save restore script")
        out.append("from EpicsCA import caput")
        xfmt = "caput('%s', %s)"        
    else:
        out.append("# Plain Save/Restore script")

    if header is not None:
        for h in header: out.append("%s %s" % (cmt,h))
        
    for pv,val in pvvals:
        out.append(xfmt  % (pv,val))
            
    return '\n'.join(out)
