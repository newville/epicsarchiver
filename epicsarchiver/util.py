#!/usr/bin/env python

import os
import toml
import time
from math import log10
from random import randint
try:
    from MySQLdb import string_literal
except:
    string_literal = str

from sqlalchemy import MetaData, create_engine, engine, text, and_
from sqlalchemy.orm import sessionmaker, Session

MAX_EPOCH = 2147483647.0   # =  2**31 - 1.0 (max unix timestamp)
SEC_DAY   = 86400.0

motor_fields = ('.VAL','.OFF','.FOFF','.SET','.HLS','.LLS',
                '.DIR','_able.VAL','.SPMG','.DESC')

valid_pvstr = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:._-+:[]<>;{}'

class Config:
    def __init__(self, **kws):
        self.logdir =  '/var/log/pvarch'

        self.server = 'mariadb'
        self.host = 'localhost'
        self.user = 'epics'
        self.password = 'change_this_password!'
        self.sql_dump = '/usr/bin/mysqldump'

        self.mail_server =  'localhost'
        self.mail_from = 'gsecars@millenia.aps.anl.gov'
        self.cache_db = 'pvarch_master'
        self.dat_prefix = 'pvdata'
        self.dat_format = '%s_%.5d'
        self.pv_deadtime_double = '5'
        self.pv_deadtime_enum = '1'
        self.cache_alert_period = '15'
        self.cache_report_period = '300'
        self.archive_report_period = '300'

        self.cache_activity_time = '10'
        self.cache_activity_min_updates =  '2'
        self.arch_activity_time = '60'
        self.arch_activity_min_updates = '2'


        self.web_baseurl = 'https://localhost/'
        self.web_url = 'pvarch'
        self.web_dir = '/var/web/pvarch'
        self.web_secret_key = 'please replace with a random string'
        self.web_admin_user = 'the right honorable foobar'
        self.web_admin_pass = 'please select a better password'
        self.web_index = 'index'
        self.web_pages = [["APS",   "StorageRing"]]

        for key, val in kws.items():
            setattr(self, key, val)

    def asdict(self):
        out = {}
        for k in dir(self):
            if (k.startswith('__') and k.endswith('__')) or  k in ('asdict', ):
                continue
            out[k] = getattr(self, k)
        return out

def get_config(envvar='EPICSARCH_CONFIG', **kws):
    """read config file defined by environmental variable EPICSARCH_CONFIG"""
    fconf = os.environ.get(envvar, None)
    conf = {}
    if fconf is not None and os.path.exists(fconf):
        conf.update(toml.load(open(fconf)))
    conf.update(kws)
    return Config(**conf)

def get_dbengine(dbname, server='sqlite', create=False,
                 user='', password='',  host='', port=None):
    """create database engine"""
    if server == 'sqlite':
        return create_engine('sqlite:///%s' % (dbname))
    elif server.startswith('maria'):
        conn_str= 'mariadb+pymysql://%s:%s@%s:%d/%s'
        if port is None:
            port = 3306
        return create_engine(conn_str % (user, password, host, port, dbname))
    elif server == 'mysql':
        #conn_str= 'mysql+mysqldb://%s:%s@%s:%d/%s'
        if port is None:
            port = 3306
        print("FAIL " , server)
        raise ValueError("no mysql")
        # return create_engine(conn_str % (user, password, host, port, dbname))

    elif server.startswith('p'):
        conn_str= 'postgresql://%s:%s@%s:%d/%s'
        if port is None:
            port = 5432
        return create_engine(conn_str % (user, password, host, port, dbname))


class DatabaseConnection:
    def __init__(self, dbname, config):
        self.dbname = dbname
        print("db " , dbname, config.server, config.host,
              config.user, config.password)
        self.engine = get_dbengine(dbname,
                                   server=config.server,
                                   user=config.user,
                                   password=config.password,
                                   host=config.host)

        self.metadata = MetaData()
        self.metadata.reflect(self.engine)
        self.conn    = self.engine.connect()
        self.tables  = self.metadata.tables
        # self.session = sessionmaker(bind=self.engine)()
        
    def execute(self, query, flush=True):
        """general execute of query"""
        result = None
        with Session(self.engine) as session, session.begin():
            result = session.execute(query)
            if flush:
                session.flush()
        return result
 
    def sql_execute(self, sql,  flush=True):
        """general execute of SQL"""
        return self.execute(text(sql), flush=flush)

    def insert(self, tablename, **kws):
        """insert to a table with keyword/value pairs"""
        tab = self.tables[tablename]
        self.execute(tab.insert().values(**kws))

    def insert_many(self, tablename, list_of_dicts):
        """make many inserts to a single table with a list of dicts"""
        
        tab = self.tables[tablename]
        with Session(self.engine) as session, session.begin():
            for kws in list_of_dicts:
                session.execute(tab.insert().values(**kws))
            session.flush()
    
    def flush(self):
        with Session(self.engine) as session, session.begin():
            session.flush()

    def add_row(self, tablename, **kws):
        """add row to a table with keyword/value pairs  == insert()"""
        self.insert(tablename, **kws)

    def table_error(self, message, tablename, funcname):
        raise ValueError(f"{message} for table '{tablename}' in {funcname}()")
        
    def handle_where(self, tablename, where=None, funcname=None, **kws):
        if funcname is None:
            funcname = 'handle_where'
        tab = self.tables.get(tablename, None)
        if tab is None:
            self.table_error("no table found", tablename, funcname)

        filters = []
        if where is None or isinstance(where, bool) and where:
            where = {}
            if len(kws) == 0:
                filters.append(True)

        if isinstance(where, int):
            if 'id' in tab.c:
                filters.append(tab.c.id==where)
            else:
                for colname, coldat in tab.columns.items():
                    if coldat.primary_key and isinstance(coldat.type, Integer):
                        filters.append(getattr(tab.c, colname)==where)
            if len(filters) == 0:
                self.table_error("could not interpret integer `where` value",
                                 tablename, funcname)
        elif isinstance(where, dict):
            where.update(kws)
            for keyname, val in where.items():
                key = getattr(tab.c, keyname, None)
                if key is None:
                    key = getattr(tab.c, "%s_id" % keyname, None)
                if key is None:
                    self.table_error(f"no column '{keyname}'", tablename, funcname)
                filters.append(key==val)
        return and_(*filters)

    def get_rows(self, tablename, where=None, order_by=None, order_desc=False,
                 limit_one=False,  none_if_empty=False, **kws):
        """general-purpose select of row data:

        Arguments
        ----------
        tablename    name of table
        where        dict of key/value pairs for where clause [None]
        order_by     name of column to order by [None]
        limit_one    whether to limit result to 1 row [False[
        none_if_empty whether to return None for an empty row [False]
        kwargs        other keyword/value pairs are included in the `where` dictionary
        Returns
        -------
        rows matching `where` (all if `where=None`) optionally ordered by order_by

        Examples
        --------
        >>> db.get_rows('element', where{'z': 30})
        """
        tab = self.tables.get(tablename, None)
        if tab is None:
            self.table_error("no table found", tablename, 'get_rows')

        where = self.handle_where(tablename, where=where, funcname='get_rows', **kws)
        query = tab.select().where(where)

        order_key = None
        if order_by is None:
            order_key = getattr(tab.c, "id", None)
        else:
            order_key = getattr(tab.c, order_by, None)
            if order_key is None:
                order_key = getattr(tab.c, f"{order_by}_id", None)
            if order_key is None:
                self.table_error(f"no column '{order_by}'", tablename, 'get_rows')
        if order_key is not None:
            if order_desc:
                order_key = order_key.desc()
            query = query.order_by(order_key)

        result = self.execute(query)
        if limit_one:
            result = result.fetchone()
        else:
            result = result.fetchall()

        if result is not None and len(result) == 0 and none_if_empty:
            result = None
        return result

    def update(self, tablename, where=None, **kws):
        """update a row (with where in a table
        using keyword args

        Arguments
        ----------
        tablename   name of table
        where       select row to update, either int for id or dict for key/val

        kws          values to update


        """
        tab = self.tables.get(tablename, None)
        if tab is None:
            self.table_error("no table found", tablename, 'update')

        where = self.handle_where(tablename, where=where, funcname='update')
        self.execute(tab.update().where(where).values(**kws))

    def delete_rows(self, tablename, where):
        """delete rows from table

        Arguments
        ----------
        tablename   name of table
        where       rows to delete, either int for id or dict for key/val
        """
        tab = self.tables.get(tablename, None)
        if tab is None:
            self.table_error("no table found", tablename, 'delete')

        where = self.handle_where(tablename, where=where, funcname='delete')
        self.execute(tab.delete().where(where))
    
        
def None_or_one(result):
    """expect result (as from query.fetchall() to return
    either None or exactly one result
    """
    if len(result) == 1:
        return result[0]
    elif len(result) ==  0:
        return None
    try:
        return result[0]
    except:
        return None


def clean_bytes(x, maxlen=4090, encoding='utf-8'):
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

def clean_string(x, maxlen=4090):
    return clean_bytes(x, maxlen=maxlen).decode('utf-8')

def safe_string(x):
    return  string_literal(x)

def clean_mail_message(s):
    "cleans a stored escaped mail message for real delivery"
    s = s.strip()
    s = s.replace("\\r","\r").replace("\\n","\n")
    s = s.replace("\\'","\'").replace("\\","").replace('\\"','\"')
    return s


def valid_pvname(pvname):
    return all([c in valid_pvstr for c in pvname])

def normalize_pvname(p):
    """ normalizes a PV name (so that it ends in .VAL if needed)."""
    pvname = clean_string(p, maxlen=128).strip()
    if '.' not in pvname:
        pvname = "%s.VAL" % pvname
    return pvname

def get_pvpair(pv1, pv2):
    "fix and sort 2 pvs for use in the pairs tables"
    p = [normalize_pvname(pv1), normalize_pvname(pv2)]
    p.sort()
    return tuple(p)

def clean_mail_message(s):
    "cleans a stored escaped mail message for real delivery"
    s = s.strip()
    s = s.replace("\\r","\r").replace("\\n","\n")
    s = s.replace("\\'","\'").replace("\\","").replace('\\"','\"')
    return s

def get_force_update_time():
    """ inserts will be forced into the Archives for stale values
    between 18 and 22 hours after last insert.
    This will spread out forced inserts, but still mean that each
    PV is recorded at least once in any 24 hour period.
    """
    return randint(18*3600, 22*3600)

def timehash():
    """ generate a simple, 10 character hash of the timestamp:
    Number of possibilites = 16^11 >~ 10^13
    the hash is a linear-in-milliseconds timestamp, so collisions
    cannot happen for 10^12 milliseconds (33 years). """
    return hex(int(10000.*time.time()))[2:-1]

def tformat(t=None,format="%Y-%b-%d %H:%M:%S"):
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


def hformat(val, length=10):
    """Format a number with '%g'-like format.

    Except that:
        a) the output string will be exactly the requested length.
        b) positive numbers will have a leading blank.
        b) the precision will be very close to as high as possible.
        c) trailing zeros will not be trimmed.

    The precision will typically be ``length-7``, with at least
    ``length-6`` significant digits.

    Parameters
    ----------
    val : float
        Value to be formatted.
    length : int, optional
        Length of output string (default is 11).

    Returns
    -------
    str
        String of specified length.

    Notes
    ------
    1. Positive values will have leading blank.

    2. Precision loss:  at values of 1.e(length-3), and at values
    of 1.e(8-length) (so at 1.e+8 and 1.e-3 for length=11)

    there will be a drop in precision as the output
    changes from 'f' to 'e' formatting:
    >>>
    >>> x = 99999995.2
    >>> print('\n'.join((hformat(x, length=11), hformat(x+10, length=11))))
     99999995.2
     1.0000e+08

    So that the reported precision drops from 9 to 6. This is inevitable
    when switching precision, we're just noting where and how it happens
    with this function.
    """
    try:
        if isinstance(val, (str, bytes)):
           val = float(clean_bytes(val))
        expon = int(log10(abs(val)))
    except (OverflowError, ValueError):
        expon = 0
    length = max(length, 7)
    form = 'e'
    prec = length - 7
    if abs(expon) > 99:
        prec -= 1
    elif ((expon > 0 and expon < (prec+6)) or
          (expon <= 0 and -expon < (prec-1))):
        form = 'f'
        prec += 4
        if expon > 0:
            prec = max(0, prec-expon)
    fmt = '{0: %i.%i%s}' % (length, prec, form)
    out = fmt.format(val)[:length]
    if out.endswith("000"):
        out = out[:-3]
    return out
