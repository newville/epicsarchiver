#!/usr/bin/env python

import os
import time
import sys

import EpicsCA

from MasterDB import MasterDB

from util import clean_input, clean_string, motor_fields, \
     normalize_pvname, tformat, valid_pvname

# def add_pv_to_cache(pvname=None,cache=None,**kw):
#     """ add a PV to the Cache and Archiver
# 
#     For a PV that is the '.VAL' field for an Epics motor will
#     automatically cause the following motor fields added as well:
#         .OFF .FOFF .SET .HLS .LLS .DIR _able.VAL .SPMG
# 
#     Each of these pairs of PVs will also be given an inital
#     'pair score' of 10, which is used to define 'related pvs'
# 
#     """
#     if pvname is None: return
#     if cache is None: cache = Cache()
#     cache.add_pv(pvname)
#     cache.close()

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
    pairs = []
    for line in lines:
        line[:-1].strip()
        if len(line)<2 or line.startswith('#'): continue
        words = line.replace(',',' ').split()
        t0 = time.time()

        # note that we suppress the setting of pair scores here
        # until we have enough PVs installed.
        for pvname in words:
            fields = cache.add_pv(pvname,set_motor_pairs=False)
            if len(fields) > 1:
                pairs.append(fields)

        
        EpicsCA.pend_event(1.e-4)
        EpicsCA.pend_io(1.0)        
        t1 = time.time()-t0
        if len(words) > 1:
            pairs.append(tuple(words[:]))

        t2 = time.time()-t0
        print ' Add PVs: [ %s ] ' % (' '.join(words))

        if len(pairs) > 100:
            print 'set a few pair scores...'
            for i in range(20):
                words = pairs.pop(0)
                cache.set_allpairs(words,score=10)
        
    print 'Waiting for all pvs requested to be put in cache....'
    # now wait for all requests to be fulfilled, and then set the remaining pair scores

    req_table= cache.db.tables['requests']
    requests_pending = True
    
    while requests_pending:
        pending_requests  = req_table.select()
        requests_pending = len(pending_requests)> 10
        time.sleep(1)
        
    print 'Finally, set remaining of pair scores:'
    while pairs:
        words = pairs.pop(0)
        cache.set_allpairs(words,score=10)
    cache.close()

    EpicsCA.pend_event(0.01)
    EpicsCA.pend_io(10.0)
    EpicsCA.cleanup()
    

class Cache(MasterDB):
    """ class for access to Master database as the Meta table of Archive databases
    """

    null_pv_value = {'value':None,'ts':0,'cvalue':None,'type':None}
    q_getfull     = "select value,cvalue,type,ts from cache where pvname='%s'"

    def __init__(self,dbconn=None,**kw):
        # use of Master assumes that there are not a lot of new PVs being
        # added to the cache so that this lookup of PVs can be done once.
        MasterDB.__init__(self,dbconn=dbconn,**kw)

        self.db.set_autocommit(1)
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
        EpicsCA.pend_io(10.0)
        if p.connected:  self.pvs[pvname] = p
        return p

    def onChanges(self,pv=None):
        if not isinstance(pv,EpicsCA.PV): return 
        self.data[pv.pvname] = (pv.value,pv.char_value,time.time(),pv.pvname)

    def update_cache(self):
        fmt = "update cache set value=%s,cvalue='%s',ts=%f where pvname='%s'"
        for (val,cval,ts,nam) in self.data.values():
            if val is None:
                pv   = self.pvs[nam]
                val  = pv.get()
                cval = pv.char_value
                ts   = time.time()
                if val is None:
                    sys.stdout.write("why does %s have value 'None'\n" % nam)
            if val is not None:
                sval = clean_string(str(val))
                self.db.execute(fmt % (sval,cval,ts,nam))
        return len(self.data)

    def connect_pvs(self):
        t0 = time.time()

        self.get_pvnames()
        npvs = len(self.pvnames)
        n_notify = 2 + (npvs / 10)
        sys.stdout.write("connecting to %i PVs\n" %  npvs)
        # print time.time()-t0
        # print 'EpicsArchiver.Cache connecting to %i PVs ' %  npvs
        for i,pvname in enumerate(self.pvnames):
            try:
                pv = EpicsCA.PV(pvname,connect=False)
                self.pvs[pvname] = pv
            except:
                sys.stderr.write('connect failed for %s\n' % pvname)

        # print 'pvs created ', time.time()-t0
        
        EpicsCA.pend_io(1.0)
        self.data = {}
        for i,pvname in enumerate(self.pvnames):
            xx = self.cache.select_one(where="pvname='%s'" % pvname)
            if xx.has_key('active'):
                if 'no' == xx['active']:  continue                
            try:
                pv = self.pvs[pvname]
                pv.connect(connect_time=1.00)
                pv.get()
                pv.set_callback(self.onChanges)
                self.data[pvname] = (pv.value, pv.char_value, time.time(),pvname)
            except KeyboardInterrupt:
                self.exit()
            except:
                sys.stderr.write('connect failed for %s\n' % pvname)

            if i % n_notify == 0:
                EpicsCA.pend_io(1.0)
                sys.stdout.write('%.2f ' % (float(i)/npvs))
                sys.stdout.flush()

        dt = time.time()-t0
        sys.stdout.write("\nconnected to %i PVs in %f seconds\n" %  (npvs,dt))
        self.update_cache()

    def set_date(self):
        t = time.time()
        s = time.ctime()
        self.info.update("process='cache'", datetime=s,ts=t)

    def get_pid(self):
        return self.get_cache_pid()

    def mainloop(self):
        " "
        sys.stdout.write('Starting Epics PV Archive Caching: \n')
        self.db.get_cursor()

        t0 = time.time()
        self.pid = os.getpid()
        self.set_cache_status('running')
        self.set_cache_pid(self.pid)
        self.set_date()

        self.connect_pvs()
        self.read_alert_settings()
        self.db.get_cursor()        
        fmt = 'pvs connected in %.1f seconds, Cache Process ID= %i\n'
        sys.stdout.write(fmt % (time.time()-t0, self.pid))
        sys.stdout.flush()

        status_str = '%s: %i values cached since last notice %i loops\n'
        ncached = 0
        nloop   = 0
        mlast   = -1
        pend_event = EpicsCA.pend_event
        pend_io    = EpicsCA.pend_io
        self.db.set_autocommit(0)
        alert_timer_on = True
        while True:
            try:
                self.db.begin_transaction()
                self.data = {}
                pend_event(1.e-3)

                n = self.update_cache()
                ncached = ncached + n
                nloop   = nloop + 1
                self.set_date()
                self.db.commit_transaction()

                tmin,tsec = time.localtime()[4:6]

                # make sure updates and alerts get processed often,
                # but not on every cycle.  Here they get processed
                # once every 15 seconds.
# 
#                 if (tsec % 15) > 7:
#                     alert_timer_on = True
#                 elif (tsec % 15) < 3 and alert_timer_on:
#                     self.process_requests()
#                     self.process_alerts()
#                     alert_timer_on = False
                self.process_requests()
                self.process_alerts()
                

                
                sys.stdout.flush()
                if self.get_pid() != self.pid:
                    sys.stdout.write('no longer master.  Exiting !!\n')
                    self.exit()

                if (tsec == 0) and (tmin != mlast) and (tmin % 5 == 0): # report once per 5 minutes
                    mlast = tmin
                    sys.stdout.write(status_str % (time.ctime(),ncached,nloop))
                    sys.stdout.flush()
                    self.read_alert_settings()
                    ncached = 0
                    nloop = 0
                    pend_io(5.0)                    

            except KeyboardInterrupt:
                return

        self.db.free_cursor()            

    def exit(self):
        self.close()
        for i in self.pvs.values(): i.disconnect()
        EpicsCA.pend_io(10.0)
        sys.exit()

    def shutdown(self):
        self.set_cache_pid(0)
        self.exit()

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
        req   = self.sql_exec_fetch("select * from requests")
        if len(req) == 0: return
        # sys.stdout.write('processing %i requests\n' %  len(req))
        del_cache= "delete from cache where %s"
        del_req  = "delete from requests where %s"
        # note: if a requested PV does not connect,
        #       wait a few minutes before dropping from
        #       the request table.
        drop_req = True

        if len(req)>0:
            sys.stdout.write("processing %i requests at %s\n" % (len(req), time.ctime()))
            sys.stdout.flush()
        es = clean_string
        now = time.time()
        
        self.db.set_autocommit(1)

        for r in req:
            nam,action,ts = r['pvname'],r['action'],r['ts']
            drop_req = True
            where = "pvname='%s'" % nam
            if valid_pvname(nam) and (now-ts < 60.0):
                if 'suspend' == action:
                    if self.pvs.has_key(nam):
                        self.pvs[nam].clear_callbacks()
                        self.cache.update(active='no',where=where)
                elif 'drop' == action:
                    if nam in self.pvnames:
                        self.sql_exec(del_cache % where)

                elif 'add' == action:
                    if nam not in self.pvnames:
                        pv = self.epics_connect(nam)
                        if pv.connected:         
                            self.add_epics_pv(pv) 
                            self.set_value(pv=pv) 
                            self.pvs[nam].set_callback(self.onChanges)                    
                        else:
                            drop_req = False
                            sys.stdout.write('could not connect to PV %s\n' % nam)

            if drop_req: self.sql_exec(del_req % where)
        self.get_pvnames()
        self.db.set_autocommit(0)

    def add_epics_pv(self,pv):
        """ add an epics PV to the cache"""
        if not pv.connected:  return

        self.get_pvnames()
        if pv.pvname in self.pvnames: return

        self.cache.insert(pvname=pv.pvname,type=pv.type)

        where = "pvname='%s'" % pv.pvname
        o = self.cache.select_one(where=where)
        if o['pvname'] not in self.pvnames:
            self.pvnames.append(o['pvname'])


    def read_alert_settings(self):
        self.alert_data = {}
        for i in self._table_alerts.select(where="active='yes'"):
            i['last_notice'] = -1.
            pvname = i.pop('pvname')
            self.alert_data[pvname] = i
        # sys.stdout.write("read alerts: %i \n" % len(self.alert_data))
        # sys.stdout.flush()
                         
    def process_alerts(self):
        # sys.stdout.write('processing alerts at %s\n' % time.ctime())
        msg = 'Alert sent for PV=%s / Label=%s to %s at %s\n'
        self.db.set_autocommit(1)
        for pvname,pvdata in self.data.items():
            if self.alert_data.has_key(pvname):
                debug = 'XRM' in pvname
                alarm = self.alert_data[pvname]
                if debug: print 'Process Alert for ', pvname, alarm['last_notice'], alarm['timeout']
                
                sendmail = (time.time() - alarm['last_notice']) > alarm['timeout']
                active   = alarm['active'] == 'yes'
                if sendmail and active:
                    if debug: print '  >>Sendmail?? ', sendmail
                    ok, notified = self.check_alert(alarm['id'],
                                                    pvdata[0],
                                                    sendmail=sendmail)
                    if debug: print '  >>check_alert: val ok? ', ok, ' notified? ', notified
                    if notified:
                        self.alert_data[pvname]['last_notice'] = time.time()
                        sys.stdout.write(msg % (pvname, alarm['name'],alarm['mailto'],time.ctime()))
                    

                if debug: print '  >>process_alert done ', self.alert_data[pvname]['last_notice']
                
        self.db.set_autocommit(0)                

                
