
#!/usr/bin/python

import time
import sys
import os
import getopt

import epics
from SimpleDB import SimpleDB
from MasterDB import MasterDB

import config
from util import normalize_pvname, get_force_update_time, tformat, \
     escape_string, clean_string, SEC_DAY, MAX_EPOCH, valid_pvname, motor_fields

class Archiver:
    MIN_TIME = 100
    sql_insert  = "insert into %s (pv_id,time,value) values (%i,%f,%s)"
    def __init__(self,dbconn=None,**args):

        self.master_db = config.master_db
        self.dbname = None
        self.db = SimpleDB(dbconn=dbconn)
        self.dbconn = self.db.conn
        # print 'Archiver db = ', self.db, self.db.conn
        
        ret = self.read_master("select db from info where process='archive'")
        self.dbname = ret[0]['db']
        # print 'Archiver:: current dbname = ', self.dbname
        # self.use_currentDB()
        self.db.use(self.dbname)        

        time.sleep(0.01)
        self.db.read_table_info()

        self.pv_table = self.db.tables['pv']
        
        self.debug  = 0
        self.force_checktime = 0
        self.messenger = sys.stdout
        self.dtime_limbo = {}

        self.last_collect = 0
        self.pvinfo = {}
        self.pvs    = {}
        for k,v in args.items():
            if   (k == 'debug'):      self.debug     = v
            elif (k == 'messenger'):  self.messenger = v

               
        for d in self.db.exec_fetch('select * from pv'):
            d.update({'last_ts': 0,'last_value':None,
                      'force_time': get_force_update_time() })
            self.pvinfo[d['name']] = d


    def exec_fetch(self,sql):
        self.db.execute(sql)
        ret = [{}]
        try:
            ret = self.db.fetchall()
        except:
            pass
        return ret

    def read_master(self,query):
        self.db.use(self.master_db)
        ret = self.exec_fetch(query)
        if self.dbname is not None: self.db.use(self.dbname)
        return ret

    def use_currentDB(self,dbname=None):
        ret = self.read_master("select db from info where process='archive'")
        try:
            self.dbname = ret[0]['db']
            self.db.use(self.dbname)
        except:
            raise IOError, 'cannot determine archive database name'
        return self.dbname
        
    def get_cache_changes(self,dt=30):
        """ get list of name,type,value,cvalue,ts from cache """
        return self.read_master("select * from cache where ts>%f" % (time.time()-dt))

    def get_cache_names(self):
        ret = self.read_master("select pvname from cache")
        self.cache_names = [i['pvname'] for i in ret]
        return self.cache_names

    def get_cache_full(self,pv):
        " return full information for a cached pv"
        s = self.read_master("select * from cache where pvname='%s'" % pv)
        if s == ():
            s  = ({'type':None,'value':None})
        return s[0]

    def refresh_pv_table(self):
        """refresh the pvinfo dictionary  by re-reading the database settings for pvs in the pv table
        This will cause changes in database settings (deadtime, etc) to be updated.
        """
        for pvdata in self.pv_table.select():
            name = pvdata['name']
            # already know about this pv: update pvinfo.
            if self.pvinfo.has_key(name):
                self.pvinfo[name].update(pvdata)
            # look up any new pvs
            else:
                self.get_info(name)

    def check_for_new_pvs(self):
        " read pvs in cache, make sure we have them all in pvinfo dictionary" 
        for p in self.get_cache_names():
            self.get_info(p)
   

    def get_info(self,pvname):
        """ return pvinfo dictionary for a pv, and also ensures that it is in the pvinfo dictionary"""
        if not self.pvinfo.has_key(pvname):
            try:
                r = self.pv_table.select_where(name=pvname)
                dat = r[0]
            except IndexError:
                self.add_pv(pvname)
                time.sleep(0.1)
                try:
                    r = self.pv_table.select_where(name=pvname)
                    dat = r[0]
                except:
                    return None

            dat['force_time']  = get_force_update_time()
            dat['last_ts']     = 0
            dat['last_value']  = None
            self.pvinfo[pvname] = dat

        return self.pvinfo[pvname]

    def sync_with_cache(self,update_vals=False):
        """ initialize pv lists, insert times, etc with cache
        use update_vals to force insert of cache values into
        the archive (as on startup)
        """
        newpvs = []
        cache_values = []
        self.get_cache_names()
        pvtable_data = self.pv_table.select()
        # print ' This is sync with cache ', update_vals, len(self.cache_names), len(pvtable_data)
        self.db.use(self.master_db)
        now = time.time()
        # print 'masterdb %s / data=%s' % ( self.master_db, len(pvtable_data))
        if update_vals:
            x = self.db.exec_fetch("select pvname,value,ts from cache")
            current_cache = {}
            for i in x:
                current_cache[i['pvname']] = i
                
        for pvdata in pvtable_data:
            name = normalize_pvname(pvdata['name'])
            
            if name not in self.cache_names:
                # print 'newpv ', name
                newpvs.append(name)            
            elif update_vals:  
                r = current_cache.get(name,None)
                if r is not None:
                    ts = r['ts']
                    if now - ts > SEC_DAY: ts = now
                    cache_values.append((name,ts,r['value']))

        if len(newpvs)>0:
            m = MasterDB()
            for p in newpvs:   m.add_pv(p)
            m.close()
        # now switch to archiving database, and (perhaps) insert values from cache
        if self.dbname is not None:
            self.db.use(self.dbname)
            for name,ts,value in cache_values: self.update_value(name,ts,value)


    def get_pv(self,pvname):
        " "
        if self.pvs.has_key(pvname): return self.pvs[pvname]
        try:
            p = self.pvs[pvname] = epics.PV(pvname)
            return p
        except:
            return None


    def dbs_for_time(self, t0=SEC_DAY, t1=MAX_EPOCH):
        """ return list of databases with data in the given time range"""
        timerange = ( min(t0,t1) - SEC_DAY, max(t0,t1) + SEC_DAY)
        query = "select * from runs where stop_time>=%i and start_time<=%i order by start_time"
        r = []
        for i in self.read_master(query % timerange):
            if i['db'] not in r: r.append(i['db'])
        return r

    def get_value_at_time(self,pvname,t):
        "return archived value of a pv at one time"
        if pvname is None: return None
        pvname = normalize_pvname(pvname)
        info = self.get_info(pvname)
        if info is None: return None

        db = self.dbs_for_time(t,t)[0]
        self.db.use(db)
        qpv  = "select data_table,id from pv where name ='%s'" % pvname
        qdat = 'select time,value from %s where pv_id=%i and time<=%f order by time desc limit 1'
        i = self.db.exec_fetchone(qpv)
        r = self.db.exec_fetchone(qdat % (i['data_table'],i['id'],t))
        return r['time'],r['value']

    def get_data(self,pvname,t0,t1,with_current=None):
        "get data from database for a time range"
        if pvname is None: return []
        pvname = normalize_pvname(pvname)
        info = self.get_info(pvname)
        if info is None:
            return ([],'No PV named %s',pvname)
            
        #
        stat   = [info]
        dat    = []
        pvquery= "select data_table,id from pv where name ='%s'" % pvname
        fquery = 'select time,value from %s where pv_id=%i and time<=%f order by time desc limit 1'
        gquery = 'select time,value from %s where pv_id=%i and time>=%f order by time limit 1'       
        squery = 'select time,value from %s where pv_id=%i and time>=%f and time<=%f order by time'

        needs_firstpoint = True
        tnow = time.time()

        # make sure t0 and t1 are ordered
        if t0 > t1:   t0,t1 = t1,t0
        if t1-t0 < 1800.0: t0 = t1 - 1800.0 # look back at least an hour

        # determine if we should append the current (cached) value
        if with_current is None:
            add_current = abs(t1-tnow) < 1.5 * SEC_DAY
        else:
            add_current = with_current
            
        # print 'get data for ' ,pvname, t0,t1
        # print 'dbs: ', self.dbs_for_time(t0,t1)
        try:
            for db in self.dbs_for_time(t0,t1):
                self.db.use(db)
                stat.append(pvquery)
                r     = self.db.exec_fetchone(pvquery)
                try:
                    table = r['data_table']
                    pvid  = r['id']
                except KeyError:  # this db doesn't know about this PV -- maybe it's a recent addition?
                    continue
                stat.append((db,table, pvid))
                if needs_firstpoint:
                    q = fquery % (table,pvid,t0)
                    stat.append(q)
                    r = self.db.exec_fetchone(q)
                    try:
                        dat.append((r['time'],r['value']))
                        needs_firstpoint = False
                    except:
                        stat.append('no data before t0!')
                q = squery % (table,pvid,t0,t1)
                stat.append(q)
                for i in self.exec_fetch(q):
                    dat.append((i['time'],i['value']))
            # add value at time just after selected time range
            r = self.db.exec_fetchone(gquery % (table,pvid,t1))
            try:
                dat.append((r['time'],r['value']))
            except KeyError:
                pass
            # optionally, add current value
            if add_current: 
                stat.append('adding cached value')
                r= self.get_cache_full(pvname)
                stat.append(r)
                if r['value'] is not None:
                    dat.append((time.time(),r['value']))
        except:
            stat.append('Exception!')
        dat.sort()
        self.use_currentDB()
        return dat,stat

    def write(self,s):
        self.messenger.write(s)
        
    def drop_pv(self,name):
        self.db.execute("update pv set active='no' where name=%s" % clean_string(name))


    def add_pv(self,name,description=None,graph={},deadtime=None,deadband=None):
        """add PV to the database: expected to take a while"""
        pvname = normalize_pvname(name)

        t0_start = time.time()
        if not valid_pvname(pvname):
            sys.stdout.write("## Archiver add_pv invalid pvname = '%s'" % pvname)
            return None

        if self.pvinfo.has_key(pvname):
            if 'yes' == self.pvinfo[pvname]['active']:
                self.write("PV %s is already in database.\n" % pvname)
            else:
                self.write("PV %s is in database, reactivating!\n" % pvname)                
                self.pvinfo[pvname]['active'] = 'yes'
            return None
        # create an Epics PV, check that it's valid

        try:
            pv = epics.PV(pvname)
            pv.connect()
            pv.get_ctrlvars()
            typ = pv.type
            count = pv.count
            prec  = pv.precision
            connected = pv.connected 
        except:
            typ= 'int'
            count = 1
            prec = None
            connected = False

        if not connected:
            self.write("cannot add PV '%s': not connected" % pvname)
            return None

        # determine type
        dtype = 'string'
        if (typ in ('int','long','short')): dtype = 'int'
        if (typ in ('enum',)):              dtype = 'enum'
        if (typ in ('double','float')):     dtype = 'double'
        
        # determine data table
        table = "pvdat%3.3i" % ((hash(pvname) % 128) + 1)
        
        # determine descrption (don't try too hard!)
        if description is None:
            if pvname.endswith('.VAL'):
                descpv  = "%s.DESC" % pvname[:-4] 
            else:
                descpv  = "%s.DESC" % pvname 
                for f in motor_fields:
                    if pvname.endswith(f):
                        descpv = None
                        
            if descpv is not None:
                try:
                    dp = epics.PV(descpv)
                    description = dp.get(as_string=True)
                ## dp.disconnect()
                except:
                    pass
        if description is None: description = ''

        # set graph default settings
        gr = {'high':'','low':'','type':'normal'}
        gr.update(graph)
        if (dtype == 'enum'):
            gr['type'] = 'discrete'
            gr['low'] = 0
            gr['high'] =  len(pv.enum_strings)
        elif dtype == 'double':
            gr['type'] = 'normal'
            dx = description.lower()
            for i in ('cathode','pirani','pressure'):
                if dx.find(i) >= 0: 
                    gr['type'] = 'log'
        
        if (deadtime == None):
            deadtime = config.pv_deadtime_dble
            if dtype in ('enum','string'):   deadtime = config.pv_deadtime_enum
            if (gr['type'] == 'log'): deadtime = 5.0  # (pressures change very frequently)

        if (deadband == None):
            deadband = 1.e-5
            if (gr['type'] == 'log'): deadband = 1.e-4
            if prec is not None: deadband = 10**(-(prec+1))
            if dtype in ('enum','string'):     deadband =  0.5
            
        self.write('Archiver adding PV: %s, table: %s' % (pvname,table))
        
        self.pv_table.insert(name    = pvname,
                             type    = dtype,
                             description= description,
                             data_table = table,
                             deadtime   = deadtime,
                             deadband   = deadband,
                             graph_lo   = gr['low'],
                             graph_hi   = gr['high'],
                             graph_type = gr['type'])

        
        dat  = self.pv_table.select_where(name=pvname)[0]
        dat['force_time'] = get_force_update_time()
        dat['last_ts'] = 0
        dat['last_value']  = None
        self.pvinfo[pvname] = dat

        self.update_value(pvname,time.time(),pv.value)

        self.write(" time=%f\n" % (time.time() - t0_start))

        sys.stdout.flush()
        pv = None        
        
    def update_value(self,name,ts,val):
        "insert value into appropriate table " 
        if val is None: return
        if ts is None or ts < self.MIN_TIME: ts = time.time()
       
        self.pvinfo[name]['last_ts'] =  ts
        self.pvinfo[name]['last_value'] =  val

        info = self.pvinfo[name]
        try:
            self.db.execute(self.sql_insert % (info['data_table'],info['id'], ts,clean_string(val)))
        except TypeError:
            self.write("cannot update %s\n" % name)

    def collect(self):
        """ one pass of collecting new values, deciding what to archive"""
        newvals, forced = {},{}
        tnow = time.time()
        dt  =  max(1.0, 3.*(tnow - self.last_collect))
        self.last_collect = tnow
        new_Changes = self.get_cache_changes(dt=dt)
        
        for dat in new_Changes:
            name  = dat['pvname']
            val   = dat['value']
            ts    = dat['ts'] or time.time()
            if not self.pvinfo.has_key(name):  self.add_pv(name)

            info = self.pvinfo[name]
            if info['active'] == 'no': continue
            if newvals.has_key(name): continue
            
            last_ts   = info['last_ts']
            last_val  = info['last_value']
            if last_ts is None:  last_ts = 0
           
            do_save = ((ts-last_ts) > info['deadtime'])
            if do_save and dat['type'] in ('double','float'):
                try:
                    v,o = float(val),float(last_val)
                    do_save = abs((v-o)/max(abs(v),abs(o),1.e-12)) > abs(info['deadband'])
                except:
                    pass
            if do_save:
                # self.update_value(name,ts,val)
                newvals[name] = (ts,val)
                if self.dtime_limbo.has_key(name): self.dtime_limbo.pop(name)
            elif (ts-last_ts) > 1.e-3:   # pv changed, but inside 'deadtime': put it in limbo!
                self.dtime_limbo[name] = (ts,val)
                
        # now look through the "limbo list" and insert the most recent change
        # iff the last insert was longer ago than the deadtime:
        tnow = time.time()
        # print '====== Collect: ', len(new_Changes) , len(newvals), len(self.dtime_limbo), time.ctime()
        for name in self.dtime_limbo.keys():
            info = self.pvinfo[name]
            if info['active'] == 'no': continue
            last_ts   = info['last_ts']
            last_val  = info['last_value']
            if (tnow - last_ts) > info['deadtime']:
                newvals[name] = self.dtime_limbo.pop(name)

        n_new     = len(newvals)
        n_forced  = 0
        # check for stale values and re-read db settings every 10 minutes or so

        if (tnow - self.force_checktime) >= 600.0:
            sys.stdout.write('looking for stale values, checking for new settings...%s\n'  %time.ctime() )
            
            self.force_checktime = tnow
            self.check_for_new_pvs()
            self.refresh_pv_table()

            for name,info in self.pvinfo.items():
                last_ts  = info['last_ts']
                last_val = info['last_value']
                if info['active'] == 'no': continue
                ftime = info['force_time']
                if tnow-last_ts > ftime:
                    r = self.get_cache_full(name)
                    if r['type'] is None and r['value'] is None: # an empty / non-cached PV?
                        try:
                            test_pv = epics.PV(name)
                            test_pv.connect()
                            # if PV is still not connected, set time
                            # to wait 2 hours before checking again.
                            if (test_pv is None or not test_pv.connected):
                                self.pvinfo[name]['last_ts'] = (7200+tnow-ftime,None)
                                self.write(" PV not connected: %s\n" % name)
                            else:
                                r['value'] = test_pv.value
                            test_pv.disconnect()
                        except:
                            pass
                    else:
                        if not newvals.has_key(name):
                            newvals[name] = (tnow,str(r['value']))
                            n_forced = n_forced + 1
                            # print 'FORCE::: ', name, tnow, r['value']

        for name,data in newvals.items():
            self.update_value(name,data[0],data[1])

        # self.db.commit_transaction()
        
        return n_new,n_forced

    def set_pidstatus(self, pid=None, status='unknown'):
        self.db.use(self.master_db)
        if status in ('running','offline','stopping','unknown'):
            self.db.execute("update info set status='%s' where process='archive'" % status)
        if pid is not None:
            self.db.execute("update info set pid=%i where process='archive'" % int(pid))
        self.db.use(self.dbname)

    def set_infotime(self,ts):
        self.db.use(self.master_db)
        self.db.execute("update info set ts=%f,datetime='%s' where process='archive'" % (ts,time.ctime(ts)))
        self.db.use(self.dbname)

    def get_pidstatus(self):
        self.db.use(self.master_db)
        ret = self.db.exec_fetchone("select * from info where process='archive'")
        self.db.use(self.dbname)
        return ret['pid'], ret['status']

    def get_nchanged(self,minutes=10,limit=None):
        """return the number of values archived in the past minutes.
        if limit is set, return as  soon as this limit is seen to be exceeded
        this is useful when checking if any values have been cached."""
        n = 0
        dt = (time.time()-minutes*60.0)
        q = "select count(time) from pvdat%3.3i where time > %f " 
        for i in range(1,129):
            r = self.exec_fetch(q % (i,dt))
            try:
                n += r[0]['count(time)']
            except:
                pass
            if limit is not None and n>limit:
                break
        return n

    def mainloop(self,verbose=False):
        t0 = time.time()
        self.db.get_cursor()
        self.use_currentDB()

        self.last_collect = t0
        self.write( 'connecting to database %s ... \n' % self.dbname)
        self.sync_with_cache(update_vals=True)

        self.write("done. DB connection took %6.3f sec\n" % (time.time()-t0))
        self.write("connecting to %i Epics PVs ... \n" % ( len(self.pvinfo) ))
        self.write('======   Start monitoring / saving to DB=%s\n' % self.dbname)
        sys.stdout.flush()
        mypid = os.getpid()
        self.set_pidstatus(pid=mypid, status='running')

        is_collecting = True
        n_loop = 0
        n_changed = 0
        n_forced  = 0
        t_lastlog = 0
        mlast = -1
        msg = "%s: %i new, %i forced entries. (%i)\n"

        while is_collecting:
            try:
                n_loop = n_loop + 1
                n1,n2 = self.collect()
                n_changed = n_changed + n1
                n_forced  = n_forced  + n2
                
                epics.poll()

                tnow = time.time()
                tmin,tsec = time.localtime()[4:6]

                if tsec < 2 and tmin != mlast and tmin % 1 == 0:
                    self.write(msg % (time.ctime(), n_changed, n_forced, n_loop))
                    sys.stdout.flush()
                    n_changed = 0
                    n_forced  = 0
                    n_loop  =  0
                    t_lastlog = tnow
                    mlast = tmin
                self.set_infotime(tnow)

            except KeyboardInterrupt:
                sys.stderr.write('Interrupted by user.\n')
                return None
            
            masterpid, status = self.get_pidstatus()

            if (status in ('stopping','offline')) or (masterpid != mypid):
                self.set_pidstatus(status='offline')
                is_collecting = False

        return None
