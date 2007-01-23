#!/usr/bin/env python

from EpicsCA import PV
from SimpleDB import SimpleDB, SimpleTable
from pvcache import PVCache, normalize_pvname
from db_connection import dbuser,dbpass,dbhost,dblogdir
import time,sys,os,getopt
import random

es = SimpleDB.escape_string

MAX_EPOCH = 2**31

def get_force_update_time():
    """ inserts will be forced for stale values between 15 and 20 hours after last insert
    this will spread out inserts, but mean that a value is written in every 24 hour period.
    """
    return 18000.0*(3.0 + random.random())

class ArchiveMaster:
    pvarch_init = ("DROP TABLE IF EXISTS PV",
                   "CREATE TABLE PV (ID  SMALLINT UNSIGNED NOT NULL PRIMARY KEY AUTO_INCREMENT,  IOC_ID  SMALLINT UNSIGNED NOT NULL,   PV_NAME VARCHAR(64) NOT NULL,   DESCRIPTION VARCHAR(128),  DATA_TABLE  VARCHAR(16),   DEADTIME  DOUBLE DEFAULT 10.0,   DEADBAND  DOUBLE DEFAULT 1.e-8,   GRAPH_HI  TINYBLOB,   GRAPH_LO  TINYBLOB,   GRAPH_TYPE  ENUM('NORMAL','LOG','DISCRETE'),   PV_TYPE ENUM('INT','DOUBLE','STRING','ENUM') NOT NULL,   UNIQUE (PV_NAME) ) TYPE=MyISAM;")


    pvdat_init = ("DROP TABLE IF EXISTS PVDAT%3.3i",
                  "CREATE TABLE PVDAT%3.3i(TIME INT UNSIGNED NOT NULL, PV_ID  SMALLINT UNSIGNED NOT NULL, VALUE TINYBLOB) TYPE=MyISAM;")

    def __init__(self):
        self.db = SimpleDB(user=dbuser,passwd=dbpass,host=dbhost,db='pvarchives')
        
    def get_currentDB(self):
        self.db.execute("select DB from CURRENT")
        return self.db.fetchone()['db']

    def save_db(self,dbname=None):
        if dbname is None: dbname = self.get_currentDB()
        self.db.use(dbname)
        self.db.safe_dump(compress=True)

        self.db.use('pvarchives')
        
    def set_runinfo(self,dbname=None):
        currdb = self.get_currentDB()
        if dbname is None: dbname = currdb
        self.db.use(dbname)
        min_time=MAX_EPOCH
        max_time=0
        for i in range(1,129):
            self.db.execute("select MIN(TIME),MAX(TIME) from PVDAT%3.3i" % (i))
            r = self.db.fetchone()
            max_time = max(max_time,r['max(time)'])
            min_time = min(min_time,r['min(time)'])
        
        if currdb == dbname:  max_time = MAX_EPOCH
        note = "%s to %s" % (time.strftime("%d-%b-%Y", time.localtime(min_time)),
                             time.strftime("%d-%b-%Y", time.localtime(max_time)))

        # print 'set run info ', dbname, note, min_time, max_time

        self.db.use('pvarchives')
        self.db.execute("UPDATE RUNS set START_TIME=%i where DB='%s'" % (min_time,dbname))
        self.db.execute("UPDATE RUNS set STOP_TIME=%i where DB='%s'"  % (max_time,dbname))
        self.db.execute("UPDATE RUNS set NOTES='%s' where DB='%s'"    % (note,dbname))

    def set_currentDB(self,dbname):
        self.db.execute("select DB from RUNS where DB=%s" % es(dbname))
        r = self.db.fetchone()
        self.db.execute("update CURRENT set DB=%s" % es(r['db']))

    def get_related_pvs(self,pv,minscore=1):
        npv = normalize_pvname(pv)        
        q = "select * from PAIRS where %s=%s and SCORE>=%i order by SCORE"
        tmp = []
        for i in ('PV1','PV2'):
            self.db.execute(q % (i,es(npv),minscore))
            for j in  self.db.fetchall(): tmp.append((j['score'],j['pv1'].strip(),j['pv2'].strip()))
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
        i = self.db.exec_fetch("select SCORE from PAIRS where PV1=%s and PV2=%s" % (es(p[0]),es(p[1])))
        try:
            return int(i[0]['score'])
        except:
            return 0

    def increment_pair_score(self,pv1,pv2):
        p = [pv1.strip(),pv2.strip()] ;  p.sort()
        score = 1 + self.get_pair_score(p[0],p[1])
        if score == 1:
            self.db.execute("insert into PAIRS VALUES (%s,%s,%i)" % (es(p[0]),es(p[1]),score))
        else:
            self.db.execute("update PAIRS set SCORE=%i where PV1=%s and PV2=%s" % (score,es(p[0]),es(p[1])))

    def set_pair_score(self,pv1,pv2,score):
        p = [pv1.strip(),pv2.strip()] ;  p.sort()
        s = self.get_pair_score(p[0],p[1])
        if s == 0:
            self.db.execute("insert into PAIRS VALUES (%s,%s,%i)" % (es(p[0]),es(p[1]),score))
        else:
            self.db.execute("update PAIRS set SCORE=%i where PV1=%s and PV2=%s" % (score,es(p[0]),es(p[1])))

    def get_all_scores(self,pv1,pv2,score):
        self.db.exec_fetch("select * from PAIRS")

    def show_status(self):
        self.db.execute("select * from CURRENT")
        r = self.db.fetchone()
        out = []
        out.append("Current Database=%s,  status=%s,  PID=%i\n" % (r['db'], r['status'],r['pid']))
        self.db.use(r['db'])
        n = []
        minutes = 10
        dt = time.time()-minutes * 60.
        for i in range(1,129):
            self.db.execute("select * from PVDAT%3.3i where TIME > %i " % (i,dt))
            n.append(len(self.db.fetchall()))
        tot = 0
        for i in n: tot = tot + i
        out.append("%i values archived in past %i minutes\n"  % (tot , minutes))
        self.db.use('pvarchives')
        return out
        
    def show_tables(self):
        self.db.execute("select * from CURRENT")
        current = self.db.fetchone()
        self.db.execute("select * from RUNS order by START_TIME desc limit 10")
        r = []
        now = time.time()
        for i in  self.db.fetchall():
            i['days'] = "%6.2f " % ((i['stop_time'] - i['start_time'])/(24*3600.0))
            if  i['db']== current['db']:
                i['days'] = "%6.2f*" % ((now - i['start_time'])/(24*3600.0))
            r.append(" %(db)s :   %(days)s      %(notes)s" % i)
        r.reverse()
        print ' =  DB       Duration(days)     Time Range '
        for i in r: print i

    def request_stop(self):
        self.set_status('STOPPING')

    def set_status(self,status='RUNNING'):
        if status not in ('RUNNING','OFFLINE','STOPPING','UNKNOWN'):
            status = 'UNKNOWN'
        self.db.execute("update CURRENT set STATUS = '%s'" % status)

    def get_status(self):
        self.db.execute("select STATUS from CURRENT")
        return self.db.fetchone()['status']

    def set_pid(self,pid=0):
        self.db.execute("update CURRENT set PID = %i" % int(pid))

    def get_pid(self):
        self.db.execute("select PID from CURRENT")
        return self.db.fetchone()['pid']

    def make_nextdb(self):
        " create a new pvarch database, copying pvs to save from an old database"

        dbname = self.get_currentDB()
        olddb = SimpleDB(user=dbuser, passwd=dbpass,db=dbname, host=dbhost,debug=0)
        olddb.use(dbname)
        olddb.execute("select * from PV")
        old_data = olddb.fetchall()

        dbname = "%s%.5i" % (dbname[:6],int(dbname[6:])+1)

        olddb.execute("drop database if exists %s" % dbname)
        olddb.execute("create database %s" % dbname)
        olddb.use(dbname)
        for i in self.pvarch_init: olddb.execute(i)
        for i in range(1,129):
            for j in self.pvdat_init: olddb.execute(j % i)
        olddb.execute("grant all privileges on %s.* to %s identified by '%s'" % (dbname,dbuser,dbpass))

        newdb = SimpleDB(user=dbuser, passwd=dbpass,db=dbname, host=dbhost,debug=0)
        pvtable = SimpleTable(newdb, table='PV',)
        print ' adding %i pvs to DB %s' % (len(old_data),dbname)

        for p in old_data:
            pvtable.insert(pv_name    =p['pv_name'],     pv_type    =p['pv_type'],
                           description=p['description'], data_table =p['data_table'],
                           deadtime   =p['deadtime'],    graph_type =p['graph_type'],
                           graph_lo   =p['graph_lo'],    graph_hi   =p['graph_hi'])


        self.db.execute("delete from RUNS where DB='%s'" % dbname)
        self.db.execute("insert into RUNS (DB,START_TIME,STOP_TIME) values ('%s',%i,%i)" % (dbname,
                                                                                     MAX_EPOCH,MAX_EPOCH))
        return dbname
    
    def dbs_for_time(self, t0=86400.0,t1=2**32):
        """ return list of databases with data in the given time range"""
        x1 = min(t0,t1)
        x2 = max(t0,t1)
        q = 'select DB from RUNS where STOP_TIME>=%i and START_TIME<=%i order by START_TIME'
        self.db.execute(q % (x1-86400.0,x2+86400.0))
        r = []
        x = self.db.fetchall()
        # print 'xx: ', x
        for i in x:
            if i['db'] not in r: r.append(i['db'])
        return r

class Archiver:
    MIN_TIME = 1000000
    def __init__(self,dbname=None,**args):
        self.dbname = dbname
        self.dbuser = dbuser
        self.dbpass = dbpass
        self.dbhost = dbhost
        self.debug  = 0
        self.force_checktime = 0
        self.messenger = sys.stdout
        self.master  = None
        for k,v in args.items():
            if   (k == 'debug'):      self.debug     = v
            elif (k == 'user'):       self.dbuser    = v
            elif (k == 'passwd'):     self.dbpass    = v
            elif (k == 'messenger'):  self.messenger = v
            elif (k == 'host'):       self.dbhost    = v
            elif (k == 'master'):     self.master    = v

        if self.master is None: self.master = ArchiveMaster()
        if self.dbname is None: self.dbname = self.master.get_currentDB()
        self.pvs    = {}
        self.pvinfo = {}
        self.last_insert = {}

        self.cache  = PVCache()
        self.is_init = False
        self.cache_names = self.cache.get_pvlist()
        
        self.db = SimpleDB(db=self.dbname,
                           user=self.dbuser,
                           passwd=self.dbpass,
                           host=self.dbhost,
                           messenger=self.messenger,
                           debug=self.debug)
        
    def initialize(self):
        self.initialize_data()
        self.check_for_new_pvs()

    def check_for_new_pvs(self):
        self.cache_names = self.cache.get_pvlist()        
        # print 'check for new pvs ', len(self.cache_names), len(self.pvinfo)
        for p in self.cache_names:
            if not self.pvinfo.has_key(p):
                self.write('adding %s to Archive\n' % p)
                self.add_pv(p)
   
    def db_for_time(self,t):
        return self.master.db_for_time(t)

    def get_pv(self,pvname):
        " "
        if pvname in self.pvs.keys(): return self.pvs[pvname]
        try:
            p = self.pvs[pvname] = PV(pvname)
            return p
        except:
            return None

    def get_data(self,pvname,t0,t1):
        "get data from database"
        if pvname is None: return []
        pvname = normalize_pvname(pvname)        
        if not pvname in self.pvinfo.keys():
            self.lookup_pvinfo(pvname)

        table,pvid,dtime,dband,ftime = self.pvinfo[pvname]

        tquery = "select DATA_TABLE,ID from PV where PV_NAME =%s"
        fquery = 'select TIME,VALUE from %s where PV_ID=%i and TIME<=%f order by TIME desc limit 1'
        squery = 'select TIME,VALUE from %s where PV_ID=%i and TIME>=%f and TIME<=%f order by TIME'
        dat = []
        has_firstpoint = False
        tnow = time.time()
        with_current=False
        if abs(t1-tnow) < 86400.0: with_current=True
        try:
            for db in self.master.dbs_for_time(t0,t1):
                self.db.use(db)
                r = self.db.exec_fetch(tquery % es(pvname))[0]
                table = r['data_table']
                pvid  = r['id']
                if not has_firstpoint:
                    r = self.db.exec_fetch(fquery % (table,pvid,t0))[0]
                    dat = [(r['time'],r['value'])]
                    has_firstpoint = True
                self.db.execute(squery % (table,pvid,t0,t1))
            r = self.db.fetchall()
            for i in r:  dat.append((i['time'],i['value']))
            if with_current:
                i = self.cache.get_full(pvname)
                dat.append((i['ts'], i['value']))
                dat.append((time.time(), i['value']))          
        except:
            pass
        dat.sort()
        return dat

    def get_related_pvs(self,pvname):
        return self.master.get_related_pvs(pvname,minscore=1)

    def increment_pair_score(self,pv1,pv2):
        npv1 = normalize_pvname(pv1)
        npv2 = normalize_pvname(pv2)
        self.master.increment_pair_score(npv1,npv2)

    def write(self,s):
        self.messenger.write(s)
        
    def drop_pv(self,name):
        self.db.execute("delete from PV where PV_NAME=%s" % name)
        
    def add_pv(self,name,description=None,graph={},deadtime=None,deadband=None):
        """add PV to the database"""
        if name is None: return
        pvname = normalize_pvname(name)
        if pvname in self.pvinfo.keys():
            self.write("PV %s is already in database.\n" % pvname)
            return None

        # create an Epics PV, check that it's valid
        try:
            pv = self.pvs[pvname] = PV(pvname)
            typ = pv.type
            count = pv.count
        except:
            typ= 'int'
            count = 1

        # determine type
        dtype = 'STRING'
        if (typ in ('int','long','short')): dtype = 'INT'
        if (typ in ('enum',)):              dtype = 'ENUM'
        if (typ in ('double','float')):     dtype = 'DOUBLE'
        
        # determine data table
        table = "PVDAT%3.3i" % ((hash(pvname) % 128) + 1)

        # determine descrption (don't try too hard!)
        if (description == None):
            if pvname.endswith('.VAL'):
                descpv  = pvname + '.DESC'
            try:
                dp = self.pvs[descpv] = PV(descpv)
                description = dp.char_value
            except:
                pass
        if description == None: description = ''

        # set graph default settings
        gr = {'high':'','low':'','type':'NORMAL'}
        gr.update(graph)
        if (dtype == 'ENUM'):
            gr['type'] = 'DISCRETE'
            gr['low'] = 0
            gr['high'] =  len(pv.enum_strings)
        elif dtype == 'DOUBLE':
            gr['type'] = 'NORMAL'
            dx = description.lower()
            for i in ('cathode','pirani','pressure'):
                if dx.find(i) >= 0: 
                    gr['type'] = 'LOG'
        
        if (deadtime == None):
            deadtime = 10.0
            if (dtype == 'ENUM'):     deadtime =  5.0  # (ENUMS take little space, rarely change)
            if (gr['type'] == 'LOG'): deadtime = 30.0  # (pressures change very frequently)

        if (deadband == None):
            deadband = 1.e-5
            if dtype in ('ENUM','STRING'):     deadband =  0.5
            if (gr['type'] == 'LOG'): deadband = 1.e-4
            
        self.db.tables['PV'].insert(pv_name    = pvname,
                                    pv_type    = dtype,
                                    description= description,
                                    data_table = table,
                                    deadtime   = deadtime,
                                    deadband   = deadband,
                                    graph_lo   = gr['low'],
                                    graph_hi   = gr['high'],
                                    graph_type = gr['type'])

        # print 'ARCHIVE  added PV ', pvname, dtype, table

        if pvname not in self.get_pvlist(): self.cache.add_pv(pvname)
        
        r = self.db.tables['PV'].select_where(pv_name=pvname)[0]
        ftime = get_force_update_time()
        self.pvinfo[pvname] = (r['data_table'],r['id'],r['deadtime'],r['deadband'], ftime)
        self.last_insert[name] = [0,None]
        
    def get_pvlist(self):
        return self.cache.get_pvlist()        

    def reread_db(self,pvname):
        ' re-read database settings for PV'
        if self.pvinfo.has_key(pvname):
            old = self.pvinfo[pvname]
            try:
                r   = self.db.tables['PV'].select_where(pv_name=pvname)[0]
                self.pvinfo[pvname] = (r['data_table'],r['id'],r['deadtime'],r['deadband'], old[4])
            except:
                pass
        else:
            self.add_pv(pvname)
    
    def lookup_pvinfo(self,pvname,pvid=None,table=None,dtime=None,dband=None):
        name = normalize_pvname(pvname)

        if pvid is None or table is None or dtime is None or dband is None:
            self.db.execute('select * from PV where PV_NAME=%s' % es(name))
            pv = self.db.fetchone()
            try:
                pvid  = pv['id']
                table = pv['data_table']
                dtime = pv['deadtime']
                dband = pv['deadband']
            except:
                return 
            
        retval = None
        if name not in self.cache_names:  retval = name
        
        ftime = get_force_update_time()
        self.pvinfo[name]      = (table,pvid,dtime,dband, ftime)
        self.last_insert[name] = (0,None)
        t0 = int(time.time() - 86400)
            
        self.db.execute("""select PV_ID,TIME,VALUE from %s where PV_ID=%i and TIME>%i ORDER BY TIME DESC LIMIT 1""" % (table, pvid,t0))
        
        d = self.db.fetchone()
        try:
            self.last_insert[name] = (d['time'],d['value'])
        except:
            r= self.cache.get_full(name)
            if r['value'] is not None:    self.update_value(name,table,pvid,r['value'])

        return retval
        # 
        
    def initialize_data(self,sync_with_cache=True):
        _for_cache = []
        self.is_init = True        
        for pv in self.db.tables['PV'].select():
            x  = self.lookup_pvinfo(pv['pv_name'],pv['id'],pv['data_table'],pv['deadtime'],pv['deadband'])
            if x is not None: _for_cache.append(x)

        if sync_with_cache:
            for i in _for_cache:
                self.cache.add_pv(i)
                


    def update_value(self,name,table,pvid,val):
        ts = time.time()
        try:
            self.db.execute("INSERT delayed into %s (PV_ID,TIME,VALUE) values (%i,%i,%s)"  %
                            (table, pvid, int(ts), es(val)))
        except TypeError:
            self.write("cannot update %s\n")
        self.last_insert[name] =  (ts,val)
        
    def get_cache_changes(self,dt=30):
        """ get list of name,type,value,cvalue,ts from cache """
        return self.cache.get_recent(dt=dt)

    def collect(self):
        newvals, forced = [],[]
        for dat in self.get_cache_changes():
            name  = dat['name']
            val   = dat['value']
            ts    = dat['ts'] or time.time()

            if name not in self.pvinfo.keys():  self.add_pv(name)
            table,pvid,dtime,dband,ftime = self.pvinfo[name]

            last_ts,last_val   = self.last_insert[name]
            if last_ts is None: last_ts = 0
            if (ts-last_ts) > dtime:
                do_save = True
                if dat['type'] in ('double','float'):
                    try:
                        do_save = abs(dband) < ( abs((float(val)-float(last_val))/
                                                     max(float(val),float(last_val),1.e-8)))
                    except:
                        pass
                if do_save:
                    self.update_value(name,table,pvid,val)
                    newvals.append((str(name),str(val)))

        if (time.time() - self.force_checktime) >= 900.0:
            # now check for stale values
            self.force_checktime = time.time()
            self.write('looking for stale values, checking for new settings...\n')
            self.check_for_new_pvs()
            for name,data in self.last_insert.items():
                last_ts,last_val = data
                self.reread_db(name)
                table,pvid,dtime,dband,ftime = self.pvinfo[name]
                tnow = time.time()
                if last_ts is None:  last_ts = 0
                if tnow-last_ts > ftime:
                    test_pv = self.get_pv(name)
                    if test_pv is None:
                        self.last_insert[name] = (tnow-ftime+7200.0,None)
                        self.write(" PV not connected: %s\n" % name)
                    else:
                        r = self.cache.get_full(name)
                        self.update_value(name,table,pvid,r['value'])
                        forced.append((str(name),str(r['value'])))
        return newvals,forced

    def show_changed(self,l,prefix=''):
        for v in l:
            self.write("%s  %.30s = %.30s  / %s\n" % (prefix,
                                                      v[0]+' '*30,
                                                      v[1]+' '*30,
                                                      time.ctime(v[2])))
        
    def mainloop(self,verbose=False):
        t0 = time.time()

        self.write( 'connecting to database %s ... \n' % self.dbname)
        self.initialize()
        
        self.write("done. DB connection took %6.3f sec\n" % (time.time()-t0))
        self.write("connecting to %i Epics PVs ... \n" % ( len(self.pvinfo) ))
        self.write('======   Start monitoring / saving to DB=%s\n' % self.dbname)

        self.master.set_status(status='RUNNING')
        mypid = os.getpid()
        self.master.set_pid(pid=mypid)
        self.master.set_runinfo()

        is_collecting = True
        n_changed = 0
        n_forced  = 0
        t_lastlog = 0
        while is_collecting:
            try:
                newvals,forced   = self.collect()
                n_changed = n_changed + len(newvals)
                n_forced  = n_forced  + len(forced)
                time.sleep(0.95)
                if verbose:
                    self.show_changed(newvals,prefix=' ')
                    self.show_changed(forced, prefix='(f) ')
                elif time.time()-t_lastlog>=59.5:
                    self.write("%s: %i new, %i forced entries.\n" % (time.ctime(), n_changed, n_forced))
                    n_changed = 0
                    n_forced  = 0
                    t_lastlog = time.time()

            except KeyboardInterrupt:
                return None
            
            status = self.master.get_status()
            if status in ('STOPPING','OFFLINE'):
                self.master.set_status('OFFLINE')
                is_collecting = False
            pid = self.master.get_pid()
            if pid != mypid: is_collecting = False

        return None
    
###

def do_collect(master=None,test=False):
    if master is None: master  = ArchiveMaster()
    
    dbname  = master.get_currentDB()
    logfile = open(os.path.join(dblogdir,"%s.log" % dbname),'a',1)

    if test:     logfile = sys.stdout
    a = Archiver(dbname=dbname,master=master,messenger=logfile)
    a.mainloop()

def do_next(master):
    dbname  = master.get_currentDB()
   
    next_db = master.make_nextdb()
    master.request_stop()
    master.set_pid(0)
    master.set_currentDB(next_db)

    time.sleep(2.0)
    do_collect(master=master)
    
    
def show_usage():
    print """pvarch:   run and interact with pvcaching / mysql process

  pvarch -h        shows this message.
  pvarch status    show archiving status.
  pvarch start     start collecting data.
  pvarch stop      stop collection.
  pvarch next      generate next db, start collecting into it.
  pvarch list      list archive databases.

"""
    sys.exit()

def main():
    opts, args = getopt.getopt(sys.argv[1:], "h", ["help"])

    try:
        cmd = args.pop(0)
    except IndexError:
        cmd = None
    for (k,v) in opts:
        if k in ("-h", "--help"): cmd = None

    m = ArchiveMaster()
    if cmd == 'status':
        for i in m.show_status(): print i
    elif cmd == 'start':     do_collect(m)
    elif cmd == 'debug':     do_collect(m,test=True)    
    elif cmd == 'next':      do_next(m)
    elif cmd == 'stop':      m.request_stop()
    elif cmd == 'list':      m.show_tables()
    elif cmd == 'save':
        if len(args)==0:     m.save_db()
        else:
            for i in args:   m.save_db(dbname=i)
    elif cmd == 'add_pv':
        for pvname in args:  m.add_pv(pvname)
    elif cmd == 'drop_pv':
        for pvname in args:  m.drop_pv(pvname)
    elif cmd == 'setrun':
        for db in args:      m.set_runinfo(db)
    else:
        show_usage()
    
if __name__ == '__main__':
    main()
    

