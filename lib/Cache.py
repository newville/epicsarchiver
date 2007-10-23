#!/usr/bin/env python

import os
import time
import sys

import EpicsCA

from MasterDB import MasterDB

from util import clean_input, clean_string, motor_fields, normalize_pvname, tformat

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
    # print 'Adding PVs listed in file ', fname
    f = open(fname,'r')
    lines = f.readlines()
    f.close()

    cache  = Cache()
    for line in lines:
        line[:-1].strip()
        if len(line)<2 or line.startswith('#'): continue
        words = line.replace(',',' ').split()
        print 'Adding PVs: %s ' % (' '.join(words))
        
        for pvname in words:
            cache.add_pv(pvname)
        EpicsCA.pend_event(0.005)
        EpicsCA.pend_io(1.0)        
        cache.set_allpairs(words,score=10)

    cache.close()
    EpicsCA.pend_event(0.01)
    EpicsCA.pend_io(10.0)
    EpicsCA.disconnect_all()
    EpicsCA.pend_io(10.0)
    
    print 'done.'

class Cache(MasterDB):
    """ class for access to Master database as the Meta table of Archive databases
    """

    null_pv_value = {'value':None,'ts':0,'cvalue':None,'type':None}
    q_getfull     = "select value,cvalue,type,ts from cache where pvname='%s'"

    def __init__(self,**kw):
        # use of Master assumes that there are not a lot of new PVs being
        # added to the cache so that this lookup of PVs can be done once.

        MasterDB.__init__(self)
        self.pid   = self.get_cache_pid()
        self._table_alerts = self.db.tables['alerts']
        self.pvs   = {}
        self.data  = {}
        
    def status_report(self,brief=False,dt=60):
        return self.cache_report(brief=brief,dt=dt)
    
    def epics_connect(self,pvname):
        if self.pvs.has_key(pvname): return self.pvs[pvname]
        
        p = EpicsCA.PV(pvname,connect=True,connect_time=1.0)
        EpicsCA.pend_event(0.01)
        EpicsCA.pend_io(2.0)
        if p.connected:  self.pvs[pvname] = p
        return p

    def onChanges(self,pv=None):
        if not isinstance(pv,EpicsCA.PV): return 
        self.data[pv.pvname] = (pv.value,pv.char_value,time.time())

    def start_group(self):
        self.data   = {}

    def end_group(self):
        for name,val in self.data.items():
            v = [clean_string(str(i)) for i in val]
            v.append(name)
            q = "update cache set value=%s,cvalue=%s,ts=%s where pvname='%s'" % tuple(v)
            self.db.execute(q)
        return len(self.data)

    def connect_pvs(self):
        self.get_pvnames()
        npvs = len(self.pvnames)
        n_notify = 2 + (npvs / 10)
        sys.stdout.write("connecting to %i PVs\n" %  npvs)
        # print 'EpicsArchiver.Cache connecting to %i PVs ' %  npvs
        for i,pvname in enumerate(self.pvnames):
            try:
                pv = EpicsCA.PV(pvname,connect=False)
                self.pvs[pvname] = pv
            except:
                sys.stderr.write('connect failed for %s\n' % pvname)
                               
        EpicsCA.pend_io(1.0)
        t0 = time.time()
        self.start_group()
        for i,pvname in enumerate(self.pvnames):
            xx = self.cache.select_one(where="pvname='%s'" % pvname)
            if xx.has_key('active'):
                if 'no' == xx['active']:  continue                
            try:
                pv = self.pvs[pvname]
                pv.connect(connect_time=5.00)
                pv.set_callback(self.onChanges)
                self.data[pvname] = (pv.value, pv.char_value, time.time())
            except KeyboardInterrupt:
                self.exit()
            except:
                sys.stderr.write('connect failed for %s\n' % pvname)
            if i % n_notify == 0:
                EpicsCA.pend_io(1.0)
                sys.stdout.write('%.2f ' % (float(i)/npvs))
                sys.stdout.flush()
        self.end_group()

    def set_date(self):
        t = time.time()
        s = time.ctime()
        self.info.update("process='cache'", datetime=s,ts=t)

    def get_pid(self):
        return self.get_cache_pid()

    def mainloop(self):
        " "
        sys.stdout.write('Starting Epics PV Archive Caching: \n')
        t0 = time.time()
        self.set_date()
        self.connect_pvs()
        self.pid = os.getpid()
        self.set_cache_status('running')
        self.set_cache_pid(self.pid)
        self.read_alert_settings()
        
        fmt = 'pvs connected in %.1f seconds, Cache Process ID= %i\n'
        sys.stdout.write(fmt % (time.time()-t0, self.pid))
        sys.stdout.flush()

        status_str = '%s: %i values cached since last notice\n'
        ncached = 0
        mlast   = -1
        while True:
            try:
                self.start_group()
                EpicsCA.pend_event(0.1)
                n = self.end_group()
                ncached = ncached + n
                self.set_date()
                self.process_requests()
                self.process_alerts()
                if self.get_pid() != self.pid:
                    sys.stdout.write('no longer master.  Exiting !!\n')
                    self.exit()
                tmin,tsec = time.localtime()[4:6]
                if tsec == 0 and (tmin != mlast): # report once per minute
                    mlast = tmin
                    sys.stdout.write(status_str % (time.ctime(),ncached))
                    sys.stdout.flush()
                    self.read_alert_settings()
                    ncached = 0
            except KeyboardInterrupt:
                return

    def exit(self):
        self.close()
        for i in self.pvs.values(): i.disconnect()
        EpicsCA.pend_io(10.0)
        sys.exit()

    def shutdown(self):
        self.set_cache_pid(0)
        time.sleep(1.0)

    def sql_exec(self,sql):
        self.db.execute(sql)

    def sql_exec_fetch(self,sql):
        self.sql_exec(sql)
        try:
            return self.db.fetchall()
        except:
            return [{}]

    def get_full(self,pv,add=False):
        " return full information for a cached pv"
        npv = normalize_pvname(pv)
        if add and (npv not in self.pvnames):
            self.add_pv(npv)
            sys.stdout.write('adding PV.....\n')
            return self.get_full(pv,add=False)
        w = self.q_getfull % npv
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
        v    = [clean_string(i) for i in [pv.value,pv.char_value,time.time()]]
        v.append(pv.pvname)
        qval = "update cache set value=%s,cvalue=%s,ts=%s where pvname='%s'" % tuple(v)
        self.db.execute(qval)
    
    def process_requests(self):
        " process requests for new PV's to be cached"
        req   = self.sql_exec_fetch("select pvname,action from requests")
        if len(req) == 0: return
        sys.stdout.write('processing %i requests\n' %  len(req))
        cmd = 'insert into cache(ts,pvname,value,cvalue) values'
        es = clean_string
        for n, r in enumerate(req):
            nam= str(r['pvname'])
            if 'suspend' == r['action']:
                if self.pvs.has_key(nam):
                    self.pvs[nam].clear_callbacks()
                    self.cache.update(active='no',
                                      where="pvname='%s'" % nam)
                    
            elif 'drop' == r['action']:
                if nam in self.pvnames:
                    self.sql_exec("delete from cache where pvname='%s'" % nam)

            elif 'add' == r['action']:
                if nam not in self.pvnames:
                    pv = self.epics_connect(nam)
                    if pv.connected:
                        self.add_epics_pv(pv) 
                        self.set_value(pv=pv) 
                        self.pvs[nam].set_callback(self.onChanges)                    
            self.sql_exec("delete from requests where pvname='%s'" % nam)
        self.get_pvnames()

    def read_alert_settings(self):
        self.alert_data = {}
        for i in self._table_alerts.select(where="active='yes'"):
            pvname = i.pop('pvname')
            self.alert_data[pvname] = i
        
    def process_alerts(self):
        for pv in self.data.keys():
            if self.alert_data.has_key(pv):
                print 'see new value for pv with an alert: ',pv
                al = self.alert_data[pv]
                print 'current alarm status = ', al['status']
                
