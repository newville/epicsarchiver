#!/usr/bin/env python
#  SQLAlchemy interface to Epics Archive

from time import time, mktime, strftime
from datetime import datetime, timedelta
from dateutil.parser import parse as dateparser
import numpy as np


from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import sessionmaker,  mapper, relationship, backref
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import  NoResultFound

import epics

from EpicsArchiver.util import normalize_pvname, MAX_EPOCH, SEC_DAY
from EpicsArchiver import __version__
# which mysql libraries are available?
MYSQL_VAR = None
try:
    import MySQLdb
    MYSQL_VAR = 'mysqldb'
except ImportError:
    try:
        import oursql
        MYSQL_VAR = 'oursql'
    except ImportError:
        try:
            import pymyql
            MYSQL_VAR = 'pymysql'
        except ImportError:
            pass

motor_fields = ('.VAL','.OFF','.FOFF','.SET','.HLS','.LLS',
                '.DIR','_able.VAL','.SPMG','.DESC')

alert_ops = {'eq': 'equal',
             'ne': 'not equal',
             'lt': 'less than',
             'gt': 'greater than',
             'le': 'less than or equal to',
             'ge': 'greater than or equal to'}

def clean_input(x, maxlen=1024):
    """clean input, forcing it to be a string, with comments stripped,
    and guarding against extra sql statements"""
    if not isinstance(x,(unicode,str)):
        x = str(x)
    if len(x) > maxlen:
        x = x[:maxlen-1]
    x.replace('#','\#')
    eol = x.find(';')
    if eol > -1:
        x = x[:eol]
    return x.strip()
                       
def safe_string(x):
    #if "'" in x:  x = escape_string(x)
    return  string_literal(x)

def get_timerange(timevar='time_ago', time_ago='1_days',
                  date1=None, date2=None):
    """returns 2 unix timestamps for a time range, based either
    on "time_ago" string or on a pair of date strings.

    Options
    --------
    timevar (string): one of 'time_ago' [default] or 'date_range'
    time_ago (string): time ago string (see Note 1)
    date1 (string):  string for initial date (see Note 2)
    date2 (string):  string for final date (see Note 2)

    Notes:
    ------
    1.  The time_ago string as the form '%f_%s'  with the
        string one of ('minutes, 'hours', or 'days'), like
             time_ago='1.5_days'   time_ago='15_minutes'

    2: 'date1' and 'date2' are strings of the form
       "%Y-%m-%d %H:%M:%S"
    """
    if (timevar.lower().startswith('date') and
        date1 is not None and
        date2 is not None):
        tmin = mktime(dateparser(date1).timetuple())
        tmax = mktime(dateparser(date2).timetuple())
        if tmin > tmax:
            tmin, tmax = tmax, tmin
    else:
        tmax   = time()
        tval, tunit = time_ago.split('_')
        opts = {}
        opts[tunit] = float(tval)
        dt_max = datetime.fromtimestamp(tmax)
        dt_min = dt_max - timedelta(**opts)
        tmin   = mktime(dt_min.timetuple())
    return tmin, tmax


def parse_times(timevar, date1, date2):
    if timevar in ('', None, 'None'):
        timevar = 'time_ago'
    time_ago = '1_days'

    # date1 could hold date1 or time_ago
    if date1  in ('', None, 'None'):
        date1 = None
    if date1 is not None and '_' in date1:
        time_ago = date1
        date1 = None

    # date2 is required for 'date range', so its absence
    # implies 'time ago'
    if date2   in ('', None, 'None'):
        date2 = None
        timevar = 'time_ago'

    if (timevar.lower().startswith('date') and
        date1 is not None and
        date2 is not None):
        tmin, tmax = get_timerange('date_range', date1=date1, date2=date2)
    else:
        tmin, tmax = get_timerange('time_ago', time_ago=time_ago)
    return tmin, tmax, date1, date2, time_ago

def convert_string_data(dat):
    """convert numpy string arrays for Waveform PVs to strings"""
    out = []
    for val in dat:
        val = val.tolist().replace('\n', '')
        val = val.replace(']', '').replace('[', ' ')
        try:
            val = [int(i) for i in val.split()]
        except:
            val = [60, 117, 110, 107, 110, 111, 119, 110, 62]
        n0 = len(val)
        if 0 in val:
            n0  = val.index(0)
        out.append(''.join([chr(int(i)) for i in val[:n0]]))
    return out


class BasicDB(object):
    """basic database interface"""
    def __init__(self, dbname=None, server='mysql',
                user='', password='', host=None, port=None):
        self.engine = None
        self.session = None
        self.metadata = None
        self.dbname = dbname
        self.conn_opts = dict(server=server, host=host, port=port,
                              user=user, password=password)
        if dbname is not None:
            self.connect(dbname, **self.conn_opts)

    def get_connector(self, server='mysql', user='', password='',
                      port=None, host=None):
        """return connection string, ready for create_engine():
             conn_string = self.get_connector(...)
             engine = create_engine(conn_string % dbname)
        """
        if host is None:
            host = 'localhost'
        conn_str = 'sqlite:///%s'
        if server.startswith('post'):
            if port is None:
                port = 5432
            conn_str = 'postgresql://%s:%s@%s:%i/%%s'
            conn_str = conn_str % (user, password, host, port)
        elif server.startswith('mysql') and MYSQL_VAR is not None:
            if port is None:
                port = 3306
            conn_str= 'mysql+%s://%s:%s@%s:%i/%%s'
            conn_str = conn_str % (MYSQL_VAR, user, password, host, port)
        return conn_str

    def connect(self, dbname, server='mysql', user='',
                password='', port=None, host=None):
        """connect to an existing pvarch_master database"""
        self.conn_str = self.get_connector(server=server, user=user,
                                           password=password,
                                           port=port, host=host)
        try:
            self.engine = create_engine(self.conn_str % self.dbname)
        except:
            raise RuntimeError("Could not connect to database")

        self.metadata =  MetaData(self.engine)
        try:
            self.metadata.reflect()
        except:
            raise RuntimeError('%s is not a valid database' % dbname)

        tables = self.tables = self.metadata.tables
        self.session = sessionmaker(bind=self.engine)()
        self.query   = self.session.query

    def close(self):
        "close session"
        self.session.commit()
        self.session.flush()
        self.session.close()

class PVDataDB(BasicDB):
    """One of the PV Archive Databases holding actual data"""
    def __init__(self, dbname=None, server= 'mysql',
                user='', password='', host=None, port=None):
        BasicDB.__init__(self, dbname=dbname, server=server,
                         user=user, password=password,
                         host=host, port=port)
        self.pvinfo = None
        if self.dbname is not None:
            self.read_pvinfo()

    def read_pvinfo(self):
        "make dictionary of PVName -> PV info (id, data_table, etc)"
        self.pvinfo = {}
        pvtab = self.tables['pv']
        for row in pvtab.select().execute().fetchall():
            n = normalize_pvname(row.name)
            self.pvinfo[n] = dict(id=row.id,
                                  desc=row.description,
                                  data_table=row.data_table,
                                  type=row.type,
                                  graph_type=row.graph_type,
                                  graph_hi=row.graph_hi,
                                  graph_lo=row.graph_lo)

    def get_data(self, pvname, tmin=None, tmax=None):
        "get data for a PV over time range"
        if self.pvinfo is None:
            self.read_pvinfo()
        pvinfo = self.pvinfo[normalize_pvname(pvname)]
        pv_id = pvinfo['id']
        dtab  = self.tables[pvinfo['data_table']]
        tnow = time()
        if tmax is None:  tmax = tnow
        if tmin is None:  tmin = tmax - SEC_DAY
        # make sure tmin and tmax are ordered, and look back at least one day
        if tmin > tmax:   tmin, tmax = tmax, tmin
        if tmin > tmax - SEC_DAY:  tmin = tmax - SEC_DAY
        q = dtab.select().where(dtab.c.pv_id==pv_id).order_by(dtab.c.time)
        q = q.where(dtab.c.time >= tmin).where(dtab.c.time <= tmax)
        return [(float(row.time), row.value) for row in q.execute().fetchall()]

class ArchiveMaster(BasicDB):
    """Archive Master"""
    def __init__(self, dbname='pvarch_master', server= 'mysql',
                user='', password='', host=None, port=None):

        BasicDB.__init__(self, dbname=dbname, server=server,
                         user=user, password=password,
                         host=host, port=port)
        self.data_dbs = {}
        self.pvinfo = {}
        self.connect_current_archive()

    def connect_current_archive(self):
        info = self.tables['info']
        q = info.select().where(info.c.process=='archive')
        row  = q.execute().fetchone()
        self.current_db = dbname = row['db']
        self.data_dbs[dbname] = tdb = PVDataDB(dbname, **self.conn_opts)
        self.pvinfo = tdb.pvinfo

    def get_pvinfo(self, pvname):
        npv = normalize_pvname(pvname)
        return self.pvinfo.get(npv, npv)


    def dbs_for_time(self, tmin=0, tmax=MAX_EPOCH):
        "return list of dbs for a selected time range"
        runs = self.tables['runs']
        q = runs.select().where(runs.c.stop_time > tmin)
        q = q.where(runs.c.start_time < tmax)
        return [row.db for row in q.execute().fetchall()]

    def related_pvs(self, pvname):
        """return list of related PVs to provided pv, in order of score"""
        ptab = self.tables['pairs']
        npv = normalize_pvname(pvname)
        pairs = []
        for r in self.query(ptab).filter((ptab.c.pv1==npv)|
                                         (ptab.c.pv2==npv)).all():
            other = (int(r.score), r.pv2)
            if npv == r.pv2: other = (int(r.score), r.pv1)
            pairs.append(other)
        pairs.sort()
        pairs.reverse()
        return [p[1] for p in pairs]

    def set_pair_score(self, pvname1, pvname2, score=None):
        """set 'relatedness' score for 2 pvs
        if score is None it will be incremented by 1
        """
        ptab = self.tables['pairs']
        npv1 = normalize_pvname(pvname1)
        npv2 = normalize_pvname(pvname2)
        q = self.query(ptab)
        pairs  = q.filter((ptab.c.pv1==npv1)&(ptab.c.pv2==npv2)).all()
        if len(pairs) == 0:
            pairs = q.filter((ptab.c.pv1==npv2)&(ptab.c.pv2==npv1)).all()

        if len(pairs) < 1:
            ptab.insert().execute(pv1=npv1, pv2=npv2, score=2)
        else:
            pair = pairs[0]
            ptab.update(whereclause='id=%i' % pair.id).execute(score=pair.score+1)

    def cache_row(self, pvname):
        """return full cache row for a pv"""
        ctab = self.tables['cache']
        npv = normalize_pvname(pvname)
        return ctab.select().where(ctab.c.pvname==npv).execute().fetchone()

    def get_data(self, pvname, tmin=None, tmax=None, with_current=None):
        """return data arrays for timestamp and value for a PV
           over the specified time range
        """
        npv = normalize_pvname(pvname)
        tnow = time()
        if tmax is None:  tmax = tnow
        if tmin is None:  tmin = tnow - SEC_DAY
        if tmin > tmax:  tmin, tmax = tmax, tmin
        # look back one day more than actually requested
        # to ensure stale data is found

        _tmax = tmax + 60
        _tmin = tmin - SEC_DAY
        ts, vals = [], []
        for dbname in self.dbs_for_time(tmin=_tmin, tmax=_tmax):
            # print("  Use DB ", dbname)
            if dbname not in self.data_dbs:
                self.data_dbs[dbname] = PVDataDB(dbname, **self.conn_opts)
            ddb = self.data_dbs[dbname]
            for t, v in ddb.get_data(npv, tmin=_tmin, tmax=_tmax):
                ts.append(float(t))
                try:
                   v = float(v)
                except:
                   pass
                vals.append(v)

        if with_current is None:
            with_current = abs(tmax-tnow) < SEC_DAY
        if with_current:
            cache = self.cache_row(npv)
            try:
               val = float(cache.value)
            except:
               val = cache.value
            # ts.append(float(cache.ts))
            # vals.append(val)
            # and current time
            ts.append(time())
            vals.append(val)

        ts, vals = np.array(ts), np.array(vals)
        torder = ts.argsort()
        ts, vals = ts[torder], vals[torder]

        # now limit date to the actually requested time range,
        # plus the one most recent previous measurement
        tsel  = np.where(ts >= tmin)[0]
        older = np.where(ts < tmin)[0]
        if len(older) > 0:
            tsel = np.concatenate(([older[-1]], tsel))
        ts, vals = ts[tsel], vals[tsel]
        return ts, vals

    def get_alerts(self):
        alerts = self.tables['alerts']
        return alerts.select().execute().fetchall()

    def add_alert(self, pvname=None, name=None,
                  mailto=None, mailmsg=None, timeout=30,
                  compare='ne', trippoint=None, **kw):
        """add  a new alert"""
        if pvname is None:
            return
        
        pvname = normalize_pvname(pvname)        
        if name is None:
            name = pvname
        if pvname not in self.pvinfo:
            self.add_pv(pvname)

        active = 'yes'
        if mailto  is None:
            active, mailto = ('no','')
        if mailmsg  is None:
            active, mailmsg= ('no','')
        if trippoint is None:
            active, trippoint = ('no', 0.)

        if compare not in alert_ops:
            compare = 'ne'
        
        alerts = self.tables['alerts']
        alerts.insert().execute(name=name, pvname=pvname, active=active,
                                mailto=mailto, mailmsg=mailmsg,
                                timeout=timeout, compare=compare,
                                trippoint=trippoint)
                  
    def update_alert(self, alertid=None, **kw):
        """modify an existing alert, index with id, and passing in
        keyword args for ('pvname','name','mailto','mailmsg',
        'trippoint','compare','status','active')
        """
        if alertid is None:
            return

        mykws = {}
        for k, v in kw.items():
            if k in ('pvname','name','mailto','mailmsg','timeout',
                     'trippoint','compare', 'active'):
                maxlen = 1024
                if k == 'mailmsg': maxlen = 32768
                v = clean_input(v, maxlen=maxlen)
                if 'compare' == k:
                    if not v in alert_ops:
                        v = 'ne'
                elif 'status' == k:
                    if v != 'ok': v = 'alarm'
                elif 'active' == k:
                    if v != 'no': v = 'yes'
                mykws[k]=v

        alerts = self.tables['alerts']                
        alerts.update(whereclause='id=%i'% alertid).execute(**mykws)


    def request_pv_cache(self, pvname):
        """request a PV to be included in caching.
        will take effect once a 'process_requests' is executed."""
        npv = normalize_pvname(pvname)
        if npv in self.pvinfo:
            return

        requests = self.tables['requests']
        requests.insert().execute(pvname=pvname, action='add', ts=time.time())

    def add_pv(self, pvname, set_motor_pairs=True):
        """adds a PV to the cache: actually requests the addition, which will
        be handled by the next process_requests in mainloop().

        Here, we check for 'Motor' PV typs and make sure all motor fields are
        requested together, and that the motor fields are 'related' by assigning
        a pair_score = 10.                
        """

        pvname = normalize_pvname(pvname.strip())
        fields = (pvname,)
        if not valid_pvname(pvname):
            return 
        
        prefix = pvname
        isMotor = False
        if pvname.endswith('.VAL'):
            prefix = pvname[:-4]

        p = epics.PV(pvname)
        p.wait_for_connection(timeout=0.25)

        if p.connected: 
            self.request_pv_cache(pvname)
            if ('.' not in prefix and p.type == 'double'):
                rtype = epics.PV(prefix+'.RTYP')
                rtype.wait_for_connection(0.1)
                if rtype is not None:
                    isMotor = 'motor' == rtype.get()
            if isMotor:
                fields.extend(["%s%s" % (prefix,i) for i in motor_fields])
                pvs = []
                for pvn in fields:
                    pvs.append(epics.PV(pvn))

                epics.poll()
                for p in pvs:
                    p.wait_for_connection(timeout=0.5)
                    if p.connected:
                        self.request_pv_cache(p.pvname)
                    
        if isMotor and set_motor_pairs:
            time.sleep(0.25)
            for f1 in fields:
                for f2 in fields:
                    if f1 != f2:
                        self.set_pair_score(f1, f2, score=10)
        return
        
    
    def status_report(self, minutes=10):
        """return a report (list of text lines) for archiving process, """
        npvs  = len(self.pvinfo)

        itab = self.tables['info']
        ainfo = itab.select().where(itab.c.process=='archive').execute().fetchone()
        cinfo = itab.select().where(itab.c.process=='cache').execute().fetchone()

        cache = self.tables['cache']
        tago = time() - 60.0
        ret = cache.select().where(cache.c.ts > tago).execute().fetchall()
        nnew = len(ret)

        out = """Cache:   status=%s, last update %s, %i PVs monitored, %i updated in past minute.
Archive: status=%s, last update %s, current database %s.""" % (
    cinfo.status, cinfo.datetime, npvs, nnew, ainfo.status, ainfo.datetime, ainfo.db)

        return {'cache_status': cinfo.status,
                'cache_date': cinfo.datetime,
                'cache_npvs': npvs,
                'cache_nupdated': nnew,
                'now': strftime("%Y-%m-%d %H:%M:%S"),
                'arch_status': ainfo.status,
                'arch_dbname': ainfo.db,
                'arch_date': ainfo.datetime}
                 

    def report_recently_archived(self, minutes=10):
        """return number of PVs archived in past N minutes
        Note:  this can be a slow process!
        """

        self.data_dbs[self.current_db]
        n = 0
        tago = time()-minutes*60.
        for i in range(1,129):
            tab = cdb.tables['pvdat%3.3i' % i]
            ret = tab.select().where(tab.c.time>=tago).execute().fetchall()
            n  += len(ret)

        return '%i new pvs in %.1f minutes' % (n, minutes)
