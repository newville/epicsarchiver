#!/usr/bin/env python
#
from MySQLdb import string_literal, escape_string

MAX_EPOCH = 2.**31
SEC_DAY   = 86400.0

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
