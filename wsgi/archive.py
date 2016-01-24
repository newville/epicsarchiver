#!/usr/bin/env python
#  SQLAlchemy interface to Epics Archive
#


import numpy as np
from datetime import datetime

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

def db_connector(server='mysql', user='', password='',
                      port=None, host=None):
    """returns db connection string, ready for create_engine():
        conn_string = db_connectionor(...)
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


class ArchiveMaster(object):
    """Archive Master"""

    def __init__(self, dbname='pvarch_master', server= 'mysql',
                user='', password='', host=None, port=None):
        self.engine = None
        self.conn_str = None
        self.session = None
        self.metadata = None
        self.dbname = dbname
        if dbname is not None:
            self.connect(dbname, server=server, user=user,
                         password=password, port=port, host=host)

    def connect(self, dbname, server='mysql', user='',
                password='', port=None, host=None):
        """connect to an existing pvarch_master database"""
        self.conn_str = db_connector(server=server, user=user,
                                    password=password, port=port, host=host)

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

    def dbs_for_time(self, tmin=0, tmax=MAX_EPOCH):
        "return list of dbs for a selected time range"
        rtab = self.tables['runs']
        q = rtab.select().where(rtab.c.start_time > tmin)
        q = q.where(rtab.c.stop_time < tmax)
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

