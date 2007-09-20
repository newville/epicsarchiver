#!/usr/bin/python

from SimpleDB import SimpleDB, SimpleTable
from config import dbuser, dbpass, dbhost, masterdb, dbprefix, dbformat
from util import normalize_pvname, escape_string, MAX_EPOCH, SEC_DAY

import time

def nextname(dbname=None,current=None):
    if dbname is None:
        index = 1
        if isinstance(current,str):
            nlen = current.find('_') + 1
            if nlen < 1:
                nlen = current.find('0')
                if nlen==-1:
                    for i,s in enumerate(current):
                        if s in '0123456789':
                            nlen = i
                            break
            index = int(current[nlen:]) + 1
        dbname = dbformat % (dbprefix,index)
    return dbname


class ArchiveMaster:
    pv_init = ("drop table if exists pv",
               """create table pv (id  smallint unsigned not null primary key auto_increment,
               ioc_id  smallint unsigned not null,
               pv_name varchar(64) not null,
               description varchar(128),
               data_table  varchar(16),
               deadtime  double default 10.0,
               deadband  double default 1.e-8,
               graph_hi  tinyblob,   graph_lo  tinyblob,
               graph_type  enum('normal','log','discrete'),
               pv_type enum('int','double','string','enum') not null,
               unique (pv_name) ) type=myisam;""")


    dat_init = ("drop table if exists dat%3.3i",
                  """create table dat%3.3i(
                  time int unsigned not null,
                  pv_id  smallint unsigned not null, value tinyblob) type=myisam;""")

    sql_pairs_order  = "select * from pairs where %s=%s and score>=%i order by score"
    sql_pairs_select = "select score from pairs where pv1=%s and pv2=%s"
    sql_pairs_update = "insert into pairs values (%s,%s,%i)"
    sql_pairs_insert = "update pairs set score=%i where pv1=%s and pv2=%s"
    sql_current_sel  = "select * from current"
    sql_set_pid      = "update current set pid=%i"
    sql_get_times    = "select min(time),max(time) from dat%3.3i"
    
    def __init__(self):
        self.db = SimpleDB(user=dbuser,passwd=dbpass,host=dbhost, db=masterdb)
        
    def __exec(self,s): self.db.execute(s)

    def __current(self,val='db'):
        self.__exec(self.sql_current_sel)
        return self.db.fetchone()[val]

    def get_currentDB(self):  self.__current('db')
    def get_status(self):     self.__current('status')
    def get_pid(self):        self.__current('pid')
    def set_pid(self,pid=0):  self.__exec(self.sql_set_pid % int(pid))

    def save_db(self,dbname=None):
        if dbname is None: dbname = self.__current('db')
        print 'saving ', dbname
        self.db.use(dbname)
        self.db.safe_dump(compress=True)
        self.db.use(masterdb)
        
    def set_runinfo(self,dbname=None):
        currdb = self.__current('db')
        if dbname is None: dbname = currdb
        self.db.use(dbname)
        min_time=MAX_EPOCH
        max_time=0
        for i in range(1,129):
            r = self.db.exec_fetchone(self.sql_get_times % (i))
            max_time = max(max_time,r['max(time)'])
            min_time = min(min_time,r['min(time)'])
        
        if currdb == dbname:  max_time = MAX_EPOCH
        note = "%s to %s" % (time.strftime("%d-%b-%Y", time.localtime(min_time)),
                             time.strftime("%d-%b-%Y", time.localtime(max_time)))

        self.db.use(masterdb)
        self.db.execute("update runs set start_time=%i where db='%s'" % (min_time,dbname))
        self.db.execute("update runs set stop_time=%i where db='%s'"  % (max_time,dbname))
        self.db.execute("update runs set notes='%s' where db='%s'"    % (note,dbname))

    def set_currentDB(self,dbname):
        r = self.db.exec_fetchone("select db from run where db=%s" % escape_string(dbname))
        self.db.execute("update current set db=%s" % escape_string(r['db']))

    def get_related_pvs(self,pv,minscore=1):
        npv = normalize_pvname(pv)        
        tmp = []
        for i in ('pv1','pv2'):
            for j in self.db.exec_fetchall(self.sql_pairs_order % (i,es(npv),minscore)):
                tmp.append((j['score'],j['pv1'].strip(),j['pv2'].strip()))
        tmp.sort()
        out = []
        for i in tmp:
            n = normalize_pvname(i[1])
            if n == npv: n =i[2]
            if n != npv and n not in out: out.append(n)
        out.reverse()
        return out


    def get_pair_score(self,pv1,pv2):
        p = [pv1.strip(),pv2.strip()] ;  p.sort()
        i = self.db.exec_fetchall(self.sql_pairs_select % (es(p[0]),es(p[1])))
        try:
            return int(i[0]['score'])
        except:
            return 0


    def set_pair_score(self,pv1,pv2,score=None):
        p = [pv1.strip(),pv2.strip()] ;  p.sort()
        current_score  = self.get_pair_score(p[0],p[1])
        if score is None: score = 1 + current_score
        if current_score == 0:
            self.db.execute(self.sql_pairs_update % (es(p[0]),es(p[1]),score))
        else:
            self.db.execute(self.sql_pairs_insert % (score,es(p[0]),es(p[1])))

    def increment_pair_score(self,pv1,pv2):  self.set_pair_score(pv1,pv2,score=None)

    def get_all_scores(self,pv1,pv2,score):  self.db.exec_fetchall("select * from pairs")


    def show_status(self):
        currdb = self.__current('db')
        out = []
        out.append("Current Database=%s,  status=%s,  PID=%i " % (currdb, self.get_status(), self.get_pid()))
        self.db.use(currdb)
        n = []
        minutes = 10
        dt = time.time()-minutes * 60.
        for i in range(1,129):
            r = self.db.exec_fetchall("select * from dat%3.3i where time > %i " % (i,dt))
            n.append(len(r))
            tot = 0
        for i in n: tot = tot + i
        out.append("%i values archived in past %i minutes"  % (tot , minutes))
        self.db.use(masterdb)
        return out
        
    def show_tables(self):
        currdb = self.__current('db')
        r = []
        timefmt = "%6.2f "
        for i in self.db.exec_fetchall("select * from runs order by start_time desc limit 10"):
            if  i['db']== currdb:
                timefmt = "%6.2f* "
                i['stop_time'] = time.time()
            i['days'] = timefmt % ((i['stop_time'] - i['start_time'])/(24*3600.0))
            r.append(" %(db)s :   %(days)s      %(notes)s" % i)
        r.reverse()
        out = [' =  DB       Duration(days)     Time Range ']
        for i in r: out.append(i)
        return out

    def request_stop(self):
        self.set_status('stopping')

    def set_status(self,status='running'):
        if status not in ('running','offline','stopping','unknown'):
            status = 'unknown'
        self.db.execute("update current set status = '%s'" % status)

    def make_nextdb(self,dbname=None):
        "create a new pvarch database, copying pvs to save from an old database"

        currdb = self.__current('db')()
        olddb  = SimpleDB(user=dbuser, passwd=dbpass,db=currdb, host=dbhost,debug=0)
        olddb.use(currdb)
        olddb.execute("select * from pv")
        old_data = olddb.fetchall()

        dbname = nextname(dbname,current=currdb)

        olddb.execute("drop database if exists %s" % dbname)
        olddb.execute("create database %s" % dbname)
        olddb.use(dbname)
        olddb.execute(self.pv_init)
        for i in range(1,129):  olddb.execute(self.dat_init)
        olddb.grant(db=dbname,user=dbuser,passwd=dbpass,host=dbhost)

        newdb = SimpleDB(user=dbuser, passwd=dbpass,db=dbname, host=dbhost,debug=0)
        pvtable = SimpleTable(newdb, table='pv')
        print ' adding %i pvs to DB %s' % (len(old_data),dbname)

        for p in old_data:
            pvtable.insert(pv_name    =p['pv_name'],     pv_type    =p['pv_type'],
                           description=p['description'], data_table =p['data_table'],
                           deadtime   =p['deadtime'],    graph_type =p['graph_type'],
                           graph_lo   =p['graph_lo'],    graph_hi   =p['graph_hi'])

        self.db.execute("delete from runs where db='%s'" % dbname)
        imax = int(MAX_EPOCH)-1
        self.db.execute("insert into runs (db,start_time,stop_time) values ('%s',%i,%i)" % (dbname,imax,imax)
        return dbname
   
    def dbs_for_time(self, t0=SEC_DAY, t1=MAX_EPOCH):
        """ return list of databases with data in the given time range"""
        timerange = ( min(t0,t1) - SEC_DAY, max(t0,t1) + SEC_DAY)
        q = 'select db from runs where stop_time>=%i and start_time<=%i order by start_time'
        r = []
        for i in self.db.exec_fetch(q % timerange):
            if i['db'] not in r: r.append(i['db'])
        return r
