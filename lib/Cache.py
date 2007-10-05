#!/usr/bin/env python

import os
import time
import types
import sys
import getopt

import EpicsCA
import config
from SimpleDB import SimpleDB
from util import clean_input, clean_string, motor_fields, normalize_pvname, set_pair_scores

def add_pv_to_cache(pvname=None,cache=None,**kw):
    """ add a PV to the Cache and Archiver

    For a PV that is the '.VAL' field for an Epics motor will
    automatically cause the following motor fields added as well:
        .OFF .FOFF .SET .HLS .LLS .DIR _able.VAL .SPMG

    Each of these pairs of PVs will also be given an inital
    'pair score' of 10, which is used to define 'related pvs'

    """
    if pvname is None: return
    if cache is None: cache = Cache()
    cache.add_pv(pvname)
    cache.close()

def add_pvfile(fname):
    """
    Read a file that lists PVs and add them (if needed) to the PV cache
    -- they will be automatically added to the running archives asap.

    The PV file generally lists one PV per line, but also has a few features:
    
       1. Putting a '.VAL' PV for a PV that is from a motor record will
          automatically have the following motor fields added:
              .VAL  .OFF .FOFF .SET .HLS .LLS .DIR _able.VAL .SPMG
          Each of these pairs of PVs will also be given an inital
          'pair score' of 10, which is used to define 'related pvs'

       2. Putting multiple PVs on a single line (space or comma delimited)
          will add all PVs on that line and also give all pairs of PVs
          on the line a 'pair score' of 10.
          
    """
    print 'Adding PVs listed in file ', fname
    f = open(fname,'r')
    lines = f.readlines()
    f.close()

    cache  = Cache()
    for line in lines:
        line[:-1].strip()
        if len(line)<2 or line.startswith('#'): continue
        words = line.replace(',',' ').split()
        print words
        for pvname in words:
            cache.add_pv(pvname)
        EpicsCA.pend_event(0.01)
        EpicsCA.pend_io(2.0)        
        set_pair_scores(words)

    cache.close()
    EpicsCA.pend_event(0.01)
    EpicsCA.pend_io(15.0)
    EpicsCA.disconnect()
    print 'done.'

class Cache:
    """ store and update a cache of PVs to a sqlite db file"""

    null_pv_value = {'value':None,'ts':0,'cvalue':None,'type':None}
    _table_names  = ("info", "req", "cache")
    q_getfull     = "select value,cvalue,type,ts from cache where name=%s"

    def __init__(self,db=None, **kw):

        self.dbname = config.cache_db

        if isinstance(db,SimpleDB):
            self.db = db
        else:
            self.db = SimpleDB(dbname=self.dbname,autocommit=1)

        self.data = {}
        self.pvs  = {}
        self.pid  = os.getpid()
        
        self.get_pvlist()        

    def close(self): self.db.close()
    
    def epics_connect(self,pvname):
        p = EpicsCA.PV(pvname,connect=True,connect_time=5.0)
        EpicsCA.pend_io(2.0)
        if not p.connected:  return False
        self.pvs[pvname] = p
        self.set_value(pv=p)
        return True

    def onChanges(self,pv=None):
        if not isinstance(pv,EpicsCA.PV): return 
        self.data[pv.pvname] = (pv.value , pv.char_value, time.time())
        
    def start_group(self):
        self.data   = {}
        self.begin_transaction()

    def end_group(self):
        nout = len(self.data)
        for nam,val in self.data.items():
            v = [clean_string(str(i)) for i in val]
            v.append(clean_string(nam))
            q = "update cache set value=%s,cvalue=%s,ts=%s where name=%s" % tuple(v)
            self.db.execute(q)
        self.commit_transaction()
        return nout

    def test_connect(self):
        self.get_pvlist()
        sys.stdout.write('EpicsArchiver.Cache connecting to %i PVs\n' %  len(self.pvlist))
        t0 = time.time()
        
        for i,pvname in enumerate(self.pvlist):  
            try:
                pv = EpicsCA.PV(pvname,connect=True,connect_time=0.25, use_numpy=False)
                self.pvs[pvname] = pv
            except KeyboardInterrupt:
                return
            except:
                sys.stderr.write('connect failed for %s\n' % pvname)
            # print i,  pvname, pv is not None, time.time()-t0
            
    def connect_pvs(self):
        self.get_pvlist()
        npvs = len(self.pvlist)
        n_notify = npvs / 10
        sys.stdout.write("connecting to %i PVs\n" %  npvs)
        # print 'EpicsArchiver.Cache connecting to %i PVs ' %  npvs
        for i,pvname in enumerate(self.pvlist):  
            try:
                pv = EpicsCA.PV(pvname,connect=False)
                self.pvs[pvname] = pv
            except:
                sys.stderr.write('connect failed for %s\n' % pvname)
                
               
        EpicsCA.pend_io(1.0)
        t0 = time.time()
        self.start_group()
        for i,pvname in enumerate(self.pvlist):
            try:
                pv = self.pvs[pvname]
                pv.connect(connect_time=5.00)
                pv.set_callback(self.onChanges)
                self.data[pvname] = (pv.value , pv.char_value, time.time())
            except KeyboardInterrupt:
                self.exit()
            except:
                sys.stderr.write('connect failed for %s\n' % pvname)
            if i % n_notify == 0:
                EpicsCA.pend_io(1.0)
                sys.stdout.write('%.2f ' % (float(i)/npvs))
                sys.stdout.flush()
        self.end_group()
        
    def testloop(self):
        " "
        sys.stdout.write('Cache test loop \n')
        
        t0 = time.time()
        self.set_date()
        self.connect_pvs()

    def mainloop(self):
        " "
        sys.stdout.write('Starting Epics PV Archive Caching: \n')
        
        t0 = time.time()
        self.set_date()
        self.connect_pvs()
        self.set_pid(self.pid)

        sys.stdout.write('\npvs connected in %.1f seconds\nCache Process ID= %i\n' % (time.time()-t0,self.pid))
        sys.stdout.flush()
        ncached = 0
        while True:
            try:
                self.start_group()
                EpicsCA.pend_event(0.05)
                self.end_group()
                ncachded = ncached + len(self.data)
                self.set_date()
                self.process_requests()
                if self.get_pid() != self.pid:
                    sys.stdout.write('no longer master.  Exiting !!\n')
                    self.exit()
                if (time.time() - t0) >= 59.5:
                    sys.stdout.write( '%s: %i values cached since last notice\n' % (time.ctime(),ncached))
                    sys.stdout.flush()
                    t0 = time.time()
                    ncached = 0
                    
            except KeyboardInterrupt:
                return

    def exit(self):
        self.close()
        for i in self.pvs.values(): i.disconnect()
        EpicsCA.pend_io(15.0)
        sys.exit()
                   
    def begin_transaction(self):
        pass # self.db.execute('begin')

    def commit_transaction(self):
        pass # self.db.execute('commit')

    def sql_exec(self,sql,commit=True):
        self.db.use(self.dbname)
        if commit: self.begin_transaction()
        self.db.execute(sql)
        if commit: self.commit_transaction()

    def sql_exec_fetch(self,sql):
        self.db.use(self.dbname)
        self.sql_exec(sql,commit=False)
        try:
            r =self.db.fetchall()
        except:
            r = [{}]
        return r

    def get_pid(self):
        t = self.sql_exec_fetch("select pid from info")
        return t[0]['pid']
    
    def set_pid(self,pid=1):
        self.sql_exec("update info set pid=%i" % pid,commit=True)

    def shutdown(self):
        self.set_pid(0)
        time.sleep(1.0)
        
    def set_date(self):
        self.sql_exec("update info set datetime=%s,ts=%f" % (clean_string(time.ctime()),time.time()),commit=True)
        
    def get_full(self,pv,add=False):
        " return full information for a cached pv"
        npv = normalize_pvname(pv)
        if add and (npv not in self.pvlist):
            self.add_pv(npv)
            sys.stdout.write('adding PV.....\n')
            return self.get_full(pv,add=False)
        w = self.q_getfull % clean_string(npv)
        try:
            
            return self.sql_exec_fetch(w)[0]
        except:
            return self.null_pv_value

    def get(self,pv,add=False,use_char=True):
        " return cached value of pv"
        ret = self.get_full(pv,add=add)
        if use_char: return ret['cvalue']
        return ret['value']

    def set_value(self,pv=None,**kws):
        # print 'Set Value ', pv, pv.value, pv.char_value, pv.pvname
        v    = [clean_string(i) for i in [pv.value,pv.char_value,time.time(),pv.pvname]]
        qval = "update cache set value=%s,cvalue=%s,ts=%s where name=%s" % tuple(v)
        self.db.execute(qval)


    def __addpv(self,pvname):
        """request a PV to be included in caching.
        will take effect once a 'process_requests' is executed."""
        if pvname not in self.pvlist:
            cmd = "insert into req(name) values (%s)" % clean_string(pvname)
            self.sql_exec(cmd,commit=True)

        
    def add_pv(self,pvname):
        """adds a PV to the cache: actually requests the addition, which will
        be handled by the next process_requests in mainloop().

        Here, we check for 'Motor' PV typs and make sure all motor fields are
        requested together, and that the motor fields are 'related' by assigning
        a pair_score = 10.                
        """
        pvname = normalize_pvname(pvname.strip())

        prefix = pvname
        if pvname.endswith('.VAL'): prefix = pvname[:-4]

        if 'motor' == EpicsCA.caget(prefix+'.RTYP'):
            fields = ["%s%s" % (prefix,i) for i in motor_fields]
            for pvname in fields:
                if EpicsCA.PV(pvname, connect=True) is not None:
                    self.__addpv(pvname)
            set_pair_scores(fields)
            EpicsCA.pend_event(0.01)
        else:
            if EpicsCA.PV(pvname,connect=True) is not None:
                self.__addpv(pvname)
        EpicsCA.pend_event(0.01)
    
    def drop_pv(self,pv):
        """delete a PV from the cache

        will take effect once a 'process_requests' is executed."""
        npv = normalize_pvname(pv)
        self.get_pvlist()
        if npv in self.pvlist:
            self.sql_exec("delete from cache where name=%s" % clean_string(npv),commit=True)
        self.get_pvlist()        
        
    def get_pvlist(self):
        " return list of pv names currently being cached"

        self.pvlist = [i['name'] for i in self.sql_exec_fetch("select name from cache")]
        return self.pvlist

    def process_requests(self):
        " process requests for new PV's to be cached"
        req   = self.sql_exec_fetch("select name from req")
        if len(req) == 0: return
        self.get_pvlist()
        sys.stdout.write('adding %i new PVs\n' %  len(req))

        self.begin_transaction()
        cmd = 'insert into cache(ts,name,value,cvalue,type) values'
        es = clean_string
        for n, r in enumerate(req):
            nam= r['name']
            if nam not in self.pvlist:
                nam = str(nam)
                valid = self.epics_connect(nam)
                if valid:
                    pv = self.pvs[nam]
                    q  = "%s (%f,%s,%s,%s,%s)" % (cmd,time.time(),
                                                  es(pv.pvname),
                                                  es(pv.value),
                                                  es(pv.char_value),
                                                  es(pv.type))

                    self.sql_exec(q,commit=False)
                    self.pvlist.append(nam)
                    self.pvs[nam].set_callback(self.onChanges)                    
                else:
                    sys.stderr.write('cache/process_req: invalid pv %s\n' % nam)
                
            self.sql_exec("delete from req where name=%s" % (es(nam)))
        self.commit_transaction()
        self.get_pvlist()

    def get_recent(self,dt=60):
        s = "select name,type,value,cvalue,ts from cache where ts> %i order by ts"
        return self.sql_exec_fetch(s % (time.time() - dt) )
        
    def status_report(self,brief=False,dt=60):
        "shows number of updated PVs in past 60 seconds"
        ret = self.get_recent(dt=dt)
        pid = self.get_pid()
        out = []
        if not brief:
            for  r in ret:
                out.append("  %s %.25s = %s" % (time.strftime("%H:%M:%S",time.localtime(r['ts'])),
                                                      r['name']+' '*20,r['value']))
        out.append('%i PVs had values updated in the past %i seconds. pid=%i' % (len(ret),dt,pid))
        return out
