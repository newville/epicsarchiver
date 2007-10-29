#!/usr/bin/python

import time
import sys
import os
import getopt

import EpicsCA
from SimpleDB import SimpleDB

from MasterDB import MasterDB
from Cache    import add_pv_to_cache

import config
from util import normalize_pvname, get_force_update_time, tformat, \
     escape_string, clean_string, SEC_DAY, MAX_EPOCH, valid_pvname

class Archiver:
    MIN_TIME = 100
    sql_insert  = "insert into %s (pv_id,time,value) values (%i,%f,%s)"

    def __init__(self,db=None,dbname=None, **args):
        
        self.master    = MasterDB()
        
        self.master_db = config.master_db
        self.dbname    = dbname
        if self.dbname is None: self.dbname = self.master.arch_db
        
        if isinstance(db,SimpleDB):
            self.db = db
        else:
            self.db = SimpleDB(dbname=self.dbname,autocommit=1)

        self.use_currentDB()
        self.db.read_table_info()
        self.pv_table = self.db.tables['pv']
        
        self.get_changes = self.master.get_recent

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

    def use_currentDB(self,dbname=None):
        if dbname is None:  dbname = self.master.arch_db
        self.dbname = dbname
        self.db.use(self.dbname)
        
    def exec_fetch(self,sql):
        self.db.execute(sql)
        ret = [{}]
        try:
            ret = self.db.fetchall()
        except:
            pass
        return ret
        
    def get_cache_names(self):
        self.cache_names = [i['pvname'] for i in self.master.cache.select()]
        return self.cache_names

    def get_cache_full(self,pv):
        " return full information for a cached pv"
        return self.master.cache.select_one(where="pvname='%s'" % pv)

    def get_cache_changes(self,dt=30):
        """ get list of name,type,value,cvalue,ts from cache """
        return self.master.get_recent(dt=dt)

    def sync_with_cache(self):
        self.pvinfo = {}
        self.last_insert = {}
        self.get_cache_names()
        for pvdata in self.pv_table.select():
            self.initialize_data(pvdata)
        self.check_for_new_pvs()

    def check_for_new_pvs(self):
        # print 'check for new pvs ', len(self.cache_names), len(self.pvinfo)
        for p in self.get_cache_names():
            if not self.pvinfo.has_key(p):
                self.write('adding %s to Archive\n' % p)
                self.add_pv(p)
   
    def get_pv(self,pvname):
        " "
        if self.pvs.has_key(pvname): return self.pvs[pvname]
        try:
            p = self.pvs[pvname] = EpicsCA.PV(pvname,connect=True)
            return p
        except:
            return None

    def get_info(self,pvname):
        r = self.pv_table.select_where(name=pvname)
        if len(r)>0: return r[0]
        return {}

    def get_value_at_time(self,pvname,t):
        "return archived value of a pv at one time"
        if pvname is None: return None
        pvname = normalize_pvname(pvname)
        if not self.pvinfo.has_key(pvname):
            self.sync_with_cache()
            if not self.pvinfo.has_key(pvname):  return None

        db = self.master.dbs_for_time(t,t)[0]
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
        if not self.pvinfo.has_key(pvname):
            self.sync_with_cache()
            if not self.pvinfo.has_key(pvname):
                return ([],'No PV named %s',pvname)
        
        #
        info   =  self.pvinfo[pvname]
        stat   = [info]
        dat    = []
        pvquery = "select data_table,id from pv where name ='%s'" % pvname
        fquery = 'select time,value from %s where pv_id=%i and time<=%f order by time desc limit 1'
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
            
        try:
            for db in self.master.dbs_for_time(t0,t1):
                self.db.use(db)
                stat.append(pvquery)
                r     = self.db.exec_fetchone(pvquery)
                table = r['data_table']
                pvid  = r['id']
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
            # add cached value if needed
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
        """add PV to the database"""
        pvname = normalize_pvname(name)
        if not valid_pvname(pvname):
            sys.stdout.write("## Archiver add_pv invalid pvname = '%s'" % pvname)
            return

        if self.pvinfo.has_key(pvname):
            if 'yes' == self.pvinfo[pvname]['active']:
                self.write("PV %s is already in database.\n" % pvname)
            else:
                self.write("PV %s is in database, reactivating!\n" % pvname)                
                self.pvinfo[pvname]['active'] = 'yes'
            return None
        # create an Epics PV, check that it's valid
        try:
            pv = EpicsCA.PV(pvname,connect=True,use_control=True)
            typ = pv.type
            count = pv.count
            prec  = pv.precision
        except:
            typ= 'int'
            count = 1
            prec = None
            
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
                descpv  = pvname[:-4] + '.DESC'
            else:
                descpv  = pvname + '.DESC'                
            try:
                dp = EpicsCA.PV(descpv,connect=True)
                description = dp.char_value
                dp.disconnect()
            except:
                pass
        if description is None: description = ''

        # device type
        devtype = None
        idot = pvname.find('.')
        if idot >0:
            try:
                dpv = EpicsCA.PV(pvname[:idot] + '.DTYP',connect=True)
                devtype = dpv.char_value
                dpv.disconnect()
            except:
                pass            
        if devtype     is None: devtype = ''

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
            
        self.write('Archiver adding PV: %s, table: %s \n' % (pvname,table))
        
        self.pv_table.insert(name    = pvname,
                             type    = dtype,
                             description= description,
                             data_table = table,
                             deadtime   = deadtime,
                             deadband   = deadband,
                             graph_lo   = gr['low'],
                             graph_hi   = gr['high'],
                             graph_type = gr['type'])

        
        self.pvinfo[pvname] = self.pv_table.select_where(name=pvname)[0]
        self.pvinfo[pvname]['force_time'] = get_force_update_time()

        self.update_value(pvname,time.time(),pv.value)

        pv.disconnect()
        # should add an insert here!!
        
    def reread_db(self,pvname):
        ' re-read database settings for PV'
        if self.pvinfo.has_key(pvname):
            try:
                self.pvinfo.update( self.pv_table.select_where(name=pvname)[0] )
            except:
                pass
        else:
            self.add_pv(pvname)
    
    def initialize_data(self,pvdata):
        name = normalize_pvname(pvdata['name'])
        if name not in self.cache_names:
            add_pv_to_cache(name)

        pvdata['force_time'] = get_force_update_time()
        self.pvinfo[name]    = pvdata
        self.last_insert[name] = (0,None)

        t0 = time.time() - SEC_DAY
        q ="select time,value from %s where pv_id=%i and time>%i order by time desc limit 1"

        db_dat = self.db.exec_fetchone(q  % (pvdata['data_table'], pvdata['id'],t0))
        if db_dat.has_key('time') and db_dat.has_key('value'):
            self.last_insert[name] = (db_dat['time'],db_dat['value'])
        else:
            r= self.get_cache_full(name)
            if r['value'] is not None and r['ts'] is not None:
                self.update_value(name,r['ts'],r['value'])
                

    def update_value(self,name,ts,val):
        "insert value into appropriate table " 
        if val is None: return
        if ts is None or ts < self.MIN_TIME: ts = time.time()
        info = self.pvinfo[name]
        self.last_insert[name] =  (ts,val)
        try:
            self.db.execute(self.sql_insert % (info['data_table'],info['id'], ts,clean_string(val)))
        except TypeError:
            self.write("cannot update %s\n" % name)


    def collect(self):
        """ one pass of collecting new values, deciding what to archive"""
        newvals, forced = [],[]
        tnow = time.time()
        dt  =  max(1.0, 3.*(tnow - self.last_collect))
        self.last_collect = tnow
        for dat in self.get_changes(dt=dt):
            name  = dat['pvname']
            val   = dat['value']
            ts    = dat['ts'] or time.time()
            if not self.pvinfo.has_key(name):  self.add_pv(name)

            info = self.pvinfo[name]
            if info['active'] == 'no': continue
            
            last_ts,last_val = self.last_insert[name]
            if last_ts is None:  last_ts = 0

            do_save = ((ts-last_ts) > info['deadtime'])
            if do_save and dat['type'] in ('double','float'):
                try:
                    v,o = float(val),float(last_val)
                    do_save = abs((v-o)/max(abs(v),abs(o),1.e-12)) > abs(info['deadband'])
                except:
                    pass
            if do_save:
                self.update_value(name,ts,val)
                newvals.append((str(name),str(val),ts))
                if self.dtime_limbo.has_key(name): self.dtime_limbo.pop(name)
            elif (ts-last_ts) > 1.e-5:   # pv changed, but inside 'deadtime': put it in limbo!
                self.dtime_limbo[name] = (ts,val)
                
        # now look through the "limbo list" and insert the most recent change
        # iff the last insert was longer ago than the deadtime:
        tnow = time.time()
        for name in self.dtime_limbo.keys():
            info = self.pvinfo[name]
            if info['active'] == 'no': continue
            last_ts,last_val  = self.last_insert[name]
            if (tnow - last_ts) > info['deadtime']:
                ts,val = self.dtime_limbo.pop(name)
                self.update_value(name,ts,val)
                newvals.append((str(name),str(val),ts))
                
        # check for stale values and re-read db settings every 10 minutes or so
        if (tnow - self.force_checktime) >= 600.0:
            self.force_checktime = tnow
            sys.stdout.write('looking for stale values, checking for new settings...\n')
            self.check_for_new_pvs()
            for name,data in self.last_insert.items():
                last_ts,last_val = data
                self.reread_db(name)
                info = self.pvinfo[name]
                if info['active'] == 'no': continue
                ftime = info['force_time']
                if tnow-last_ts > ftime:
                    r = self.get_cache_full(name)
                    if r['type'] is None and r['value'] is None: # an empty / non-cached PV?
                        try:
                            test_pv = EpicsCA.PV(name,connect=True)
                            # if PV is still not connected, set time
                            # to wait 2 hours before checking again.
                            if (test_pv is None or not test_pv.connected):
                                self.last_insert[name] = (7200+tnow-ftime,None)
                                self.write(" PV not connected: %s\n" % name)
                            else:
                                r['value'] = test_pv.value
                            test_pv.disconnect()
                        except:
                            pass
                    else:
                        self.update_value(name,tnow,r['value'])
                        forced.append((str(name),str(r['value']),tnow))
                    
        return newvals,forced

    def show_changed(self,l,prefix=''):
        for v in l:
            self.write("%s  %.30s = %.30s  / %s\n" % (prefix, v[0]+' '*30,
                                                      v[1]+' '*30, time.ctime(v[2])))
        
    def set_pidstatus(self, pid=None, status='unknown'):
        if status in ('running','offline','stopping','unknown'):
            self.master.set_arch_status(status)
            
        if pid is not None:
            self.write(" setting pid to %i\n" % pid)
            self.master.set_arch_pid(pid)
        
    def get_pidstatus(self):
        pid = self.master.get_arch_pid()
        status = self.master.get_arch_status()        
        return pid, status

    def mainloop(self,verbose=False):
        t0 = time.time()
        self.last_collect = t0
        self.write( 'connecting to database %s ... \n' % self.dbname)
        self.sync_with_cache()
        
        self.write("done. DB connection took %6.3f sec\n" % (time.time()-t0))
        self.write("connecting to %i Epics PVs ... \n" % ( len(self.pvinfo) ))
        self.write('======   Start monitoring / saving to DB=%s\n' % self.dbname)

        mypid = os.getpid()
        self.set_pidstatus(pid=mypid, status='running')

        is_collecting = True
        n_changed = 0
        n_forced  = 0
        t_lastlog = 0
        while is_collecting:
            try:
                newvals,forced   = self.collect()
                n_changed = n_changed + len(newvals)
                n_forced  = n_forced  + len(forced)
                EpicsCA.pend_event(0.10)
                tnow = time.time()
                if verbose:
                    self.show_changed(newvals,prefix=' ')
                    self.show_changed(forced, prefix='(f) ')
                elif tnow-t_lastlog>=299.5:
                    self.write("%s: %i new, %i forced entries.\n" % (time.ctime(),
                                                                     n_changed, n_forced))
                    sys.stdout.flush()
                    n_changed = 0
                    n_forced  = 0
                    t_lastlog = tnow

                self.master.info.update("process='archive'",ts=tnow,datetime=time.ctime())

            except KeyboardInterrupt:
                sys.stderr.write('Interrupted by user.\n')
                return None
            
            masterpid, status = self.get_pidstatus()

            if (status in ('stopping','offline')) or (masterpid != mypid):
                self.set_pidstatus(status='offline')
                is_collecting = False

        return None
