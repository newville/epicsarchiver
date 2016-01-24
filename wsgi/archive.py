#!/usr/bin/env python
#  SQLAlchemy interface to Epics Archive
#


import numpy as np
from datetime import datetime

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import sessionmaker,  mapper, relationship, backref
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import  NoResultFound

from EpicsArchiver.util import normalize_pvname
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
##


class _BaseTable(object):
    "generic class to encapsulate SQLAlchemy table"
    def __repr__(self):
        name = self.__class__.__name__
        fields = ['%s' % getattr(self, 'name', 'UNNAMED')]
        return "<%s(%s)>" % (name, ', '.join(fields))

class Cache(_BaseTable):
    pass

class Pairs(_BaseTable):
    pass

class Info(_BaseTable):
    pass

class Runs(_BaseTable):
    pass

class Requests(_BaseTable):
    pass

class Alerts(_BaseTable):
    pass

class ArchiveMaster(object):
    """Archive Master"""

    def __init__(self, dbname='pvarch_master', server= 'mysql',
                user='', password='', host=None, port=None):
        self.engine = None
        self.session = None
        self.metadata = None
        if dbname is not None:
            self.connect(dbname, server=server, user=user,
                         password=password, port=port, host=host)

    def connect(self, dbname, server='mysql', user='',
                password='', port=None, host=None):
        """connect to an existing pvarch_master database"""
        if host is None:
            host = 'localhost'
        self.dbname = dbname
        self.engine = None
        print 'Connect:  ', user, server, MYSQL_VAR
        if server.startswith('sqlit'):
            self.engine = create_engine('sqlite:///%s' % self.dbname)
        elif server.startswith('post'):
            conn_str= 'postgresql://%s:%s@%s:%i/%s'
            if port is None: port = 5432                
            self.engine = create_engine(conn_str % (user, password, host,
                                                    port, dbname))

        elif server.startswith('mysql') and MYSQL_VAR is not None:
            conn_str= 'mysql+%s://%s:%s@%s:%i/%s'
            if port is None: port = 3306
            self.engine = create_engine(conn_str % (MYSQL_VAR,
                                                    user, password, host,
                                                    port, dbname))
            
        if self.engine is None:
            raise RuntimeError("Could not connect to database")
        
        self.metadata =  MetaData(self.engine)
        try:
            self.metadata.reflect()
        except:
            raise RuntimeError('%s is not a valid database' % dbname)

        tables = self.tables = self.metadata.tables
        self.session = sessionmaker(bind=self.engine)()
        self.query   = self.session.query

        mapper(Info,    tables['info'])
        mapper(Cache,   tables['cache'])
        mapper(Pairs,   tables['pairs'])
        mapper(Runs,    tables['runs'])
        mapper(Alerts,  tables['alerts'])
        mapper(Requests, tables['requests'])

    def close(self):
        "close session"
        self.session.commit()
        self.session.flush()
        self.session.close()

    def get_related_pvs(self, pvname):
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

