#!/usr/bin/env python
#  SQLAlchemy interface to Epics Archive

import time
from datetime import datetime
import numpy as np

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import sessionmaker,  mapper, relationship, backref
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import  NoResultFound

from EpicsArchiver.util import normalize_pvname, MAX_EPOCH, SEC_DAY


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
        tnow = time.time()
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
        out = []
        for r in self.query(ptab).filter((ptab.c.pv1==npv)|
                                         (ptab.c.pv2==npv)).all():
            other = r.pv2
            if npv == r.pv2: other = r.pv1
            out.append(other)
        return out

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
        tnow = time.time()
        if tmax is None:
            tmax = tnow
        if tmin is None:
            tmin = tnow - SEC_DAY
        if tmin > tmax:
            tmin, tmax = tmax, tmin

        # look back one day more than actually requested
        # to ensure stale data is found
        _tmax = tmax + 60
        _tmin = tmin - SEC_DAY
        ts, vals = [], []
        for dbname in self.dbs_for_time(tmin=_tmin, tmax=_tmax):
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
            ts.append(float(cache.ts))
            try:
               val = float(cache.value)
            except:
               val = cache.value
            vals.append(val)
            # and this value at current time
            ts.append(time.time())
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
