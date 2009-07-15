#!/usr/bin/env python
#
import time
from MySQLdb import string_literal, escape_string

MAX_EPOCH = 2147483647.0   # =  2**31 - 1.0 (max unix timestamp)
SEC_DAY   = 86400.0

motor_fields = ('.VAL','.OFF','.FOFF','.SET','.HLS','.LLS',
                '.DIR','_able.VAL','.SPMG','.DESC')

valid_pvstr = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:._'

def clean_input(x,maxlen=None):
    """clean input, forcing it to be a string, with comments stripped,
    and guarding against extra sql statements"""
    if not isinstance(x,(unicode,str)): x = str(x)

    if maxlen is None: maxlen = 1024
    if len(x) > maxlen:   x = x[:maxlen-1]
    x.replace('#','\#')
    eol = x.find(';')
    if eol > -1: x = x[:eol]
    return x.strip()
                       
def safe_string(x):
    # if "'" in x:  x = escape_string(x)
    return  string_literal(x)

def clean_string(x,maxlen=None):
    x = clean_input(x,maxlen=maxlen)
    return safe_string(x)

def normalize_pvname(p):
    """ normalizes a PV name (so that it ends in .VAL if needed)."""
    x = clean_input(p.strip())
    if len(x) > 2 and x.find('.') < 1: return '%s.VAL' % x
    return x

def clean_mail_message(s):
    "cleans a stored escaped mail message for real delivery"
    s = s.strip()
    s = s.replace("\\r","\r").replace("\\n","\n")
    s = s.replace("\\'","\'").replace("\\","").replace('\\"','\"')
    return s
    
def get_force_update_time():
    """ inserts will be forced into the Archives for stale values
    between 18 and 21 hours after last insert.
    This will spread out inserts, and means that every PV is
    recorded at least once in any 24 hour period.  
    """
    from random import randint
    return 3 * (21600  + randint(0,3600))
    # return (10800 + randint(0,3600))
    # return 2 * (120  + randint(0,720))

def timehash():
    """ generate a simple, 10 character hash of the timestamp:
    Number of possibilites = 16^11 >~ 10^13
    the hash is a linear-in-milliseconds timestamp, so collisions
    cannot happen for 10^12 milliseconds (33 years). """ 
    return hex(long(10000.*time.time()))[2:-1]

def tformat(t=None,format="%Y-%m-%d %H:%M:%S"):
    """ time formatting"""
    if t is None: t = time.time()
    return time.strftime(format, time.localtime(t))

def time_sec2str(sec=None):
    return tformat(t=sec,format="%Y-%m-%d %H:%M:%S")
        
def time_str2sec(s):
    s = s.replace('_',' ')
    xdat,xtim=s.split(' ')
    dates = xdat.split('-')
    times = xtim.split(':')

    (yr,mon,day,hr,min,sec,x,y,tz) = time.localtime()
    if   len(dates)>=3:  yr,mon,day = dates
    elif len(dates)==2:  mon,day = dates
    elif len(dates)==1:  day = dates[0]        
    
    min,sec = 0,0
    if   len(times)>=3:  hr,min,sec = times
    elif len(times)==2:  hr,min  = times
    elif len(times)==1:  hr  = times[0]

    return time.mktime((int(yr),int(mon),int(day),int(hr),int(min), int(sec),0,0,tz))

def valid_pvname(pvname):
    for c in pvname:
        if c not in valid_pvstr: return False
    return True

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
