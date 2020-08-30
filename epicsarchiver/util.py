#!/usr/bin/env python
#
import os
import toml
import time
from random import randint
from MySQLdb import string_literal
from sqlalchemy import MetaData, create_engine, engine, text
from sqlalchemy.orm import sessionmaker

MAX_EPOCH = 2147483647.0   # =  2**31 - 1.0 (max unix timestamp)
SEC_DAY   = 86400.0

motor_fields = ('.VAL','.OFF','.FOFF','.SET','.HLS','.LLS',
                '.DIR','_able.VAL','.SPMG','.DESC')

valid_pvstr = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:._-+:[]<>;{}'

class Config:
    logdir =  '/var/log/pvarch'
    baseurl = 'https://localhost/'

    db_server = 'mysql'
    db_host = 'localhost'
    db_user = 'epics'
    db_password = 'change_this_password!'
    db_dump = 'usr/bin/mysqldump -opt'

    mail_server =  'localhost'
    mail_from = 'pvarchiver@aps.anl.gov'
    master_db = 'pvarch_master'
    dat_prefix = 'pvdata'
    dat_format = '%s_%.5d'
    pv_deadtime_double = 5
    pv_deadtime_enum = 1


def get_config(envvar='PVARCH_CONFIG'):
    """read config file defined by environmental variable PVARCH_CONFIG"""
    conf = {'logdir': '/var/log/pvarch',
            'baseurl': 'https://localhost/',
            'mail_server':  'localhost',
            'mail_from': 'pvarchiver@aps.anl.gov',
            'db_server': 'mysql',
            'db_host': 'localhost',
            'db_user': 'epics',
            'db_password': 'change_this_password!',
            'db_dump': 'usr/bin/mysqldump -opt',
            'master_db': 'pvarch_master',
            'dat_prefix': 'pvdata',
            'dat_format': '%s_%.5d',
            'pv_deadtime_double': 5,
            'pv_deadtime_enum': 1}

    fconf = os.environ.get(envvar, None)
    if fconf is not None and os.path.exists(fconf):
        conf.update(toml.load(open(fconf)))
    config = Config()
    for k, v in conf.items():
        settar(config, k, v)
    return config

def get_dbengine(dbname, server='sqlite', create=False,
                 user='', password='',  host='', port=None):
    """create database engine"""
    if server == 'sqlite':
        return create_engine('sqlite:///%s' % (dbname))
    elif server == 'mysql':
        conn_str= 'mysql+mysqldb://%s:%s@%s:%d/%s'
        if port is None:
            port = 3306
        return create_engine(conn_str % (user, password, host, port, dbname))

    elif server.startswith('p'):
        conn_str= 'postgresql://%s:%s@%s:%d/%s'
        if port is None:
            port = 5432
        return create_engine(conn_str % (user, password, host, port, dbname))


class DatabaseConnection:
    def __init__(self, dbname, config, autocommit=True):
        self.dbname = dbname
        self.engine = get_dbengine(dbname,
                                   server=config.db_server,
                                   user=config.db_user,
                                   password=config.db_password,
                                   host=config.db_host)
        
        self.metadata = MetaData(self.engine)
        self.metadata.reflect()
        self.conn    = self.engine.connect()
        self.session = sessionmaker(bind=self.engine, autocommit=autocommit)()
        self.tables  = self.metadata.tables

    def flush(self):
        self.session.flush()

def None_or_one(result):
    """expect result (as from query.fetchall() to return 
    either None or exactly one result
    """
    if isinstance(result, engine.result.ResultProxy):
        return result
    try:
        return result[0]
    except:
        return None

   
def clean_bytes(x, maxlen=4096, encoding='utf-8'):
    """
    clean data as a string with comments stripped,
    guarding against extra sql statements, 
    and force back to bytes object / utf-8
    """
    if isinstance(x, bytes):
        x = x.decode(encoding)
    if not isinstance(x, str):
        x = str(x)
    for char in (';', '#'):
        eol = x.find(char)
        if eol > -1:
            x = x[:eol]
    return x.strip().encode(encoding)

def clean_string(x, maxlen=4096):
    return clean_bytes(x, maxlen=maxlen).decode('utf-8')

def safe_string(x):
    return  string_literal(x)

def clean_mail_message(s):
    "cleans a stored escaped mail message for real delivery"
    s = s.strip()
    s = s.replace("\\r","\r").replace("\\n","\n")
    s = s.replace("\\'","\'").replace("\\","").replace('\\"','\"')
    return s

def normalize_pvname(p):
    """ normalizes a PV name (so that it ends in .VAL if needed)."""
    x = clean_string(p.strip())
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
    between 18 and 22 hours after last insert.
    This will spread out inserts, and means that every PV is
    recorded at least once in any 24 hour period.  
    """
    return 64800 + (4 * randint(0, 3600))

def timehash():
    """ generate a simple, 10 character hash of the timestamp:
    Number of possibilites = 16^11 >~ 10^13
    the hash is a linear-in-milliseconds timestamp, so collisions
    cannot happen for 10^12 milliseconds (33 years). """ 
    return hex(int(10000.*time.time()))[2:-1]

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
        out.append("from epics import caput")
        xfmt = "caput('%s', %s)"        
    else:
        out.append("# Plain Save/Restore script")

    if header is not None:
        for h in header: out.append("%s %s" % (cmt,h))
        
    for pv,val in pvvals:
        out.append(xfmt  % (pv,val))
            
    return '\n'.join(out)
