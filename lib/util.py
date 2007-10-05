#!/usr/bin/env python
#
import time
from MySQLdb import string_literal, escape_string

MAX_EPOCH = 2147483647.0   # =  2**31 - 1.0 (max unix timestamp)
SEC_DAY   = 86400.0

motor_fields = ('.VAL','.OFF','.FOFF','.SET','.HLS','.LLS','.DIR','_able.VAL','.SPMG')

def clean_input(x,maxlen=256):
    """clean input, forcing it to be a string, with comments stripped,
    and guarding against extra sql statements"""
    if not isinstance(x,str): x = str(x)

    if len(x)>maxlen:   x = x[:maxlen-1]

    eol = max(x.find('#'),x.find(';'))
    if eol > 0: x = x[:eol]
    return x
                       
def clean_string(x):
    x = clean_input(x)
    if "'" in x:  return  '"%s"' %  escape_string(x)
    return  string_literal(x)

def normalize_pvname(p):
    """ normalizes a PV name (so that it ends in .VAL if needed)."""
    x = clean_input(p)
    if x.find('.') < 1: return '%s.VAL' % x
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


def set_pair_scores(pvlist):
    """ set (or check) that all pairs of pvs in list pvlist have a 'pair score'"""
    if not isinstance(pvlist,(list,tuple)): return
    if len(pvlist)< 2: return
    from Master import ArchiveMaster

    m = ArchiveMaster()
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
    from Master import ArchiveMaster
    m = ArchiveMaster()
    out = m.get_related_pvs(normalize_pvname(pvname),minscore=1)
    m.close()
    m = None
    return out

def increment_pair_score(pv1,pv2):
    from Master import ArchiveMaster    
    m = ArchiveMaster()
    m.increment_pair_score(normalize_pvname(pv1),normalize_pvname(pv2))
    m.close()
    m = None

