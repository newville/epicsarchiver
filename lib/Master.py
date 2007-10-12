#!/usr/bin/python

import time
from MasterDB import MasterDB
from SimpleDB import SimpleDB, SimpleTable
from config   import dbuser, dbpass, dbhost, master_db, dat_prefix, dat_format
from util     import normalize_pvname, clean_string, tformat, MAX_EPOCH, SEC_DAY


def nextname(current=None,dbname=None):
    if dbname is not None: return dbname
    index = 1
    if isinstance(current,str):
        nlen = current.rfind('_') + 1
        if nlen < 1:
            nlen = current.find('0')
            if nlen==-1:
                import string
                for i,s in enumerate(current):
                    if s in string.digits:
                        nlen = i
                        break
        index = int(current[nlen:]) + 1
    return dat_format % (dat_prefix,index)

class ArchiveMaster(MasterDB):
    """ class for access to Master database as the Meta table of Archive databases
    """
    pv_init = ("drop table if exists pv",
               """create table pv (id  smallint unsigned not null primary key auto_increment,
               name        varchar(64) not null unique,
               description varchar(128),          data_table  varchar(16),
               deadtime    double default 10.0,   deadband    double default 1.e-8,
               graph_hi    tinyblob,              graph_lo    tinyblob,
               graph_type  enum('normal','log','discrete'),
               type        enum('int','double','string','enum') not null,
               active   enum('yes','no') default 'yes')""")

    dat_init = ("drop table if exists pvdat%3.3i",
                """create table pvdat%3.3i( time   double not null,
                pv_id  smallint unsigned not null, value  tinyblob);""")

    sql_get_times   = "select min(time),max(time) from pvdat%3.3i"
    
    def __init__(self):
        # use of MasterDB assumes that there are not a lot of new PVs being
        # added to the cache so that this lookup of PVs can be done once.
        MasterDB.__init__(self)

    def stop_archiver(self):
        self.set_arch_status('stopping')

    def save_db(self,dbname=None):
        if dbname is None: dbname = self.arch_db
        sys.stdout.write('saving %s\n' % dbname)
        self.db.use(dbname)
        self.db.safe_dump(compress=True)
        self.db.use(master_db)

    def __setrun(self,dbname,t0=None,t1=None):
        if t0 is None: t0 = time.time()
        if t1 is None: t1 = MAX_EPOCH
        dbstr = clean_string(dbname)
        r = self.runs.select_one(where = "db=%s" % dbstr)['db']
        if r == {}:
            self.runs.insert(db=dbstr)

        notes = clean_string("%s to %s" % (tformat(t0), tformat(t1)))

        where = "db=%s" % (dbstr)
        self.runs.update(start_time=t0,  where=where)
        self.runs.update(stop_time=t1,   where=where)
        self.runs.update(notes=notes,    where=where)
        
    def set_runinfo(self,dbname=None):
        if dbname is None: dbname = self.arch_db
        self.db.use(dbname)
        min_time=MAX_EPOCH
        max_time=0
        for i in range(1,129):
            r = self.db.exec_fetchone(self.sql_get_times % (i))
            try:
                mx = r['max(time)'] or max_time
                mn = r['min(time)'] or min_time
                max_time = max(max_time,mx)
                min_time = min(min_time,mn)
            except TypeError:
                pass
        
        if dbname == self.arch_db:  max_time = MAX_EPOCH
        self.__setrun(dbname,min_time,max_time)
        self.db.use(master_db)
    
    def set_currentDB(self,dbname):
        dbstr = clean_string(dbname)        
        self.__setrun(dbname)
        self.info.update(db=dbstr,where="process='archive'")

    def create_emptydb(self,dbname):
        self.db.execute("drop database if exists %s" % dbname)
        self.db.execute("create database %s" % dbname)
        self.db.use(dbname)
        self.db.execute(self.pv_init)
        for i in range(1,129):
            for q in self.dat_init: self.db.execute(q % i)
        self.db.grant(db=dbname,user=dbuser,passwd=dbpass,host=dbhost)
        self.db.use(master_db)

    def make_nextdb(self,dbname=None):
        "create a new pvarch database, copying pvs to save from an old database"

        olddb  = SimpleDB(user=dbuser, passwd=dbpass,dbname=self.arch_db, host=dbhost,debug=0)
        olddb.use(self.arch_db)
        old_data = olddb.tables['pv'].select()

        dbname = nextname(current=self.arch_db,dbname=dbname)
        self.create_emptydb(dbname)
        
        newdb = SimpleDB(user=dbuser, passwd=dbpass,dbname=dbname, host=dbhost,debug=0)
        pvtable = SimpleTable(newdb, table='pv')
        sys.stdout.write('adding %i pvs to DB %s\n' % (len(old_data),dbname))

        for p in old_data:
            if p['active'] == 'no': continue
            pvtable.insert(name       =p['name'],        type    =p['type'],
                           description=p['description'], data_table =p['data_table'],
                           deadtime   =p['deadtime'],    graph_type =p['graph_type'],
                           graph_lo   =p['graph_lo'],    graph_hi   =p['graph_hi'])

        self.__setrun(dbname)
        olddb.close()
        newdb.close()        
        return dbname
        
    def dbs_for_time(self, t0=SEC_DAY, t1=MAX_EPOCH):
        """ return list of databases with data in the given time range"""
        timerange = ( min(t0,t1) - SEC_DAY, max(t0,t1) + SEC_DAY)
        where = "stop_time>=%i and start_time<=%i order by start_time"
        r = []
        for i in self.runs.select(where=where % timerange):
            if i['db'] not in r: r.append(i['db'])
        return r
        
