#!/usr/bin/env python

import os
import time
import sys

import epics
from debugtime import debugtime
from MasterDB import MasterDB

from util import clean_input, clean_string, motor_fields, \
     normalize_pvname, tformat, valid_pvname

def add_pv(pvname=None,cache=None,**kw):
    """ add a PV to the Cache and Archiver

    For a PV that is the '.VAL' field for an Epics motor will
    automatically cause the following motor fields added as well:
        .OFF .FOFF .SET .HLS .LLS .DIR _able.VAL .SPMG

    Each of these pairs of PVs will also be given an inital
    'pair score' of 10, which is used to define 'related pvs'
    """
    if pvname is None:
        return
    if cache is None:
        cache = Cache()
    cache.add_pv(pvname)
    time.sleep(0.05)
    print("Wait for PV %s to get to cache...")

    cache.process_requests()

    req_table= cache.db.tables['requests']
    requests_pending = True
    while requests_pending:
        pending_requests  = req_table.select()
        requests_pending = len(pending_requests) > 2
        time.sleep(1.0)
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
    pairs = []
    for line in lines:
        line[:-1].strip()
        if len(line)<2 or line.startswith('#'): continue
        words = line.replace(',',' ').split()
        t0 = time.time()

        # note that we suppress the setting of pair scores here
        # until we have enough PVs installed.
        for pvname in words:
            fields = cache.add_pv(pvname, set_motor_pairs=False)
            if len(fields) > 1:
                pairs.append(fields)
        cache.process_requests()
        epics.poll()

        t1 = time.time()-t0
        if len(words) > 1:
            pairs.append(tuple(words[:]))

        t2 = time.time()-t0
        print ' Add PVs: [ %s ] ' % (' '.join(words))

        if len(pairs) > 100:
            print 'set a few pair scores...'
            for i in range(20):
                words = pairs.pop(0)
                cache.set_allpairs(words, score=10)

    print 'Waiting for all pvs requested to be put in cache....'
    # now wait for all requests to be fulfilled, and then set the remaining pair scores

    req_table= cache.db.tables['requests']
    requests_pending = True

    while requests_pending:
        pending_requests  = req_table.select()
        requests_pending = len(pending_requests) > 2
        time.sleep(1)

    # print 'Finally, set remaining of pair scores:'
    while pairs:
        words = pairs.pop(0)
        cache.set_allpairs(words,score=10)
    cache.close()

    time.sleep(0.01)
    epics.poll(evt=0.01,iot=5.0)


class Cache(MasterDB):
    """ class for access to Master database as the Meta table of Archive databases
    """

    null_pv_value = {'value':None,'ts':0,'cvalue':None,'type':None}
    q_getfull     = "select value,cvalue,type,ts from cache where pvname='%s'"

    def __init__(self,dbconn=None,pidfile='/tmp/cache.pid', **kw):
        # use of Master assumes that there are not a lot of new PVs being
        # added to the cache so that this lookup of PVs can be done once.
        MasterDB.__init__(self,dbconn=dbconn,**kw)

        self.db.set_autocommit(1)
        self.pid   = self.get_cache_pid()
        self.pidfile = pidfile
        self._table_alerts = self.db.tables['alerts']
        self.pvs   = {}
        self.data  = {}
        self.alert_data = {}
        self.db.set_autocommit(0)
        self.last_update = 0

    def status_report(self,brief=False,dt=60):
        return self.cache_report(brief=brief,dt=dt)

    def epics_connect(self,pvname):
        if self.pvs.has_key(pvname):
            return self.pvs[pvname]

        p = epics.PV(pvname)
        epics.poll()
        if p.connected:
            self.pvs[pvname] = p
        return p

    def onChanges(self, pvname=None, value=None, char_value=None,
                  timestamp=None, **kw):
        if value is not None and pvname is not None:
            if timestamp is None:
                timestamp = time.time()
            self.data[pvname] = (value, char_value, timestamp)
            if  pvname in self.alert_data:
                self.alert_data[pvname]['last_value'] = value

    def update_cache(self):
        t0 = time.time()
        fmt = "update cache set value=%s,cvalue=%s,ts=%s where pvname=%s"
        self.db.cursor.execute("start transaction")
        updates = []
        # take keys as of right now, and pop off the latest values
        # for these pvs.   Be careful to NOT set self.data = {} as
        # this can blow away any changes that occur during this i/io
        for nam in self.data.keys():
            val, cval, ts = self.data.pop(nam)
            val = str(val)
            if ';' in val:  #
                val = val[:val.find(';')]
                if len(val) > 250: # must fit in tinyblob!
                    val = val[:250]
            updates.append((val, cval, ts, nam))

        self.db.cursor.executemany(fmt, updates)
        self.db.cursor.execute("commit")
        self.set_date()
        return len(updates)

    def look_for_unconnected_pvs(self):
        """ look for PVs that have no callbacks defined --
        must have been unconnected -- but are now connected"""
        nout = 0
        for pvname in self.pvnames:
            pv = self.pvs[pvname]
            if pv is None:
                nout = nout + 1
                continue
            if not pv.connected:
                time.sleep(0.0025)
                if not pv.connected:
                    nout = nout + 1

            if pv.connected and len(pv.callbacks) < 1:
                pv.add_callback(self.onChanges)
                self.data[pvname] = (pv.value, pv.char_value, time.time())
        return nout

    def connect_pvs(self, npvs=None):
        d = debugtime()
        self.get_pvnames()
        if npvs is None:
            npvs = len(self.pvnames)
        elif npvs < len(self.pvnames):
            self.pvnames = self.pvnames[:npvs]
        n_notify = npvs / 10
        d.add("connecting to %i PVs" %  npvs)
        for pvname in self.pvnames:
            try:
                self.pvs[pvname] = epics.PV(pvname,
                                            connection_timeout=1.0)
            except epics.ca.ChannelAccessException:
                sys.stderr.write(' Could not create PV %s \n' % pvname)
        d.add('Created %i PV Objects' % len(self.pvs), verbose=False)

        time.sleep(0.0001*npvs)
        epics.ca.poll()
        unconn = 0
        for pv in self.pvs.values():
            if not pv.connected:
                time.sleep(0.002)
                if not pv.connected:
                    unconn =  unconn + 1

        epics.ca.poll()
        d.add("Connected to PVs (%i not connected)" %  unconn, verbose=False)
        self.data = {}
        for pv in self.pvs.values():
            if pv is not None and pv.connected:
                cval = pv.get(as_string=True)
                self.data[pv.pvname] = (pv.value, cval, time.time())

        d.add("got initial values for PVs", verbose=False)
        #for pvname, vals in self.data.items():
        #    print pvname, vals
        self.last_update = 0
        self.update_cache()
        d.add("Entered values for %i PVs to Db" %  npvs)
        for i, pv in enumerate(self.pvs.values()):
            if pv is not None and pv.connected:
                pv.add_callback(self.onChanges)
        d.add("added callbacks for PVs")
        #
        unconn =self.look_for_unconnected_pvs()
        d.add("looked for unconnected pvs: %i not connected" % unconn)
        d.show()


    def set_date(self):
        self.last_update = t = time.time()
        s = time.ctime()
        self.info.update("process='cache'", datetime=s,ts=t)

    def get_pid(self):
        return self.get_cache_pid()

    def mainloop(self, npvs=None):
        " "
        sys.stdout.write('Starting Epics PV Archive Caching: \n')
        self.db.get_cursor()

        t0 = time.time()
        self.pid = os.getpid()
        self.db.set_autocommit(1)
        self.set_cache_status('running')
        self.set_cache_pid(self.pid)

        fout = open(self.pidfile, 'w')
        fout.write('%i\n' % self.pid)
        fout.close()
        self.db.set_autocommit(0)
        self.read_alert_settings()
        self.db.get_cursor()
        self.connect_pvs(npvs=npvs)
        fmt = 'pvs connected, ready to run. Cache Process ID= %i\n'
        sys.stdout.write(fmt % self.pid)

        status_str = '%s: %i values cached since last notice %i loops\n'
        ncached = 0
        nloop_count = 0
        mlast   = -1
        self.db.set_autocommit(0)
        alert_timer_on = True
        while True:
            try:
                # self.db.begin_transaction()
                epics.poll(evt=1.e-4, iot=1.0)
                n = self.update_cache()
                ncached +=  n
                nloop_count   +=  1
                # self.db.commit_transaction()
                tmin, tsec = time.localtime()[4:6]

                # make sure updates and alerts get processed often,
                # but not on every cycle.  Here they get processed
                # once every 15 seconds.
                if (tsec % 15) > 10:
                    alert_timer_on = True
                elif (tsec % 15) < 3 and alert_timer_on:
                    self.process_requests()
                    self.process_alerts()
                    alert_timer_on = False

                sys.stdout.flush()
                if self.get_pid() != self.pid:
                    sys.stdout.write('  No longer master! Exiting %i / %i !!\n' % (self.pid, self.get_pid()))
                    self.exit()
                if (tsec == 0) and (tmin != mlast) and (tmin % 5 == 0): # report once per 5 minutes
                    mlast = tmin
                    sys.stdout.write(status_str % (time.ctime(),ncached,nloop_count))
                    sys.stdout.flush()
                    self.read_alert_settings()
                    self.look_for_unconnected_pvs()
                    ncached = 0
                    nloop_count = 0

            except KeyboardInterrupt:
                return

        self.db.free_cursor()

    def exit(self):
        self.close()
        for i in self.pvs.values():
            i.disconnect()

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
        if len(self.pvnames)== 0: self.get_pvnames()
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
        if len(req) == 0:
            return

        del_cache= "delete from cache where %s"

        # note: if a requested PV does not connect,
        #       wait a few minutes before dropping from
        #       the request table.

        if len(req)>0:
            sys.stdout.write("processing %i requests at %s\n" % (len(req), time.ctime()))
            sys.stdout.flush()
        es = clean_string
        sys.stdout.write( 'Process Req: %i\n' % len(self.pvnames))
        if len(self.pvnames)== 0:
            self.get_pvnames()
        sys.stdout.write( 'Process Req: %i\n' % len(self.pvnames))

        now = time.time()
        self.db.set_autocommit(1)
        drop_ids = []
        for r in req:
            nam, rid, action, ts = r['pvname'], r['id'], r['action'], r['ts']
            where = "pvname='%s'" % nam
            print 'Request: ', nam, rid, action
            if valid_pvname(nam) and (now-ts < 3000.0):
                if 'suspend' == action:
                    if self.pvs.has_key(nam):
                        self.pvs[nam].clear_callbacks()
                        self.cache.update(active='no',where=where)
                        drop_ids.append(rid)
                elif 'drop' == action:
                    if nam in self.pvnames:
                        self.sql_exec(del_cache % where)
                        drop_ids.append(rid)

                elif 'add' == action:
                    if nam not in self.pvnames:
                        pv = self.epics_connect(nam)
                        xval = pv.get(as_string=True)
                        conn = pv.wait_for_connection(timeout=1.0)
                        if conn:
                            self.add_epics_pv(pv)
                            self.set_value(pv=pv)
                            pv.add_callback(self.onChanges)
                            self.pvs[nam] = pv
                            drop_ids.append(rid)
                            sys.stdout.write('added PV = %s\n' % nam)
                        else:
                            sys.stdout.write('could not connect to PV %s\n' % nam)
                    else:
                        print '? already in self.pvnames ', nam
                        drop_ids.append(rid)
            else:
                drop_ids.append(rid)

        time.sleep(0.01)
        self.get_pvnames()
        for rid in drop_ids:
            self.sql_exec( "delete from requests where id=%i" % rid )

        time.sleep(0.01)
        self.db.set_autocommit(0)

    def add_epics_pv(self,pv):
        """ add an epics PV to the cache"""
        if not pv.connected:
            print 'add_epics_pv: NOT CONNECTED ', pv
            return

        self.get_pvnames()
        if pv.pvname in self.pvnames:
            return
        self.cache.insert(pvname=pv.pvname,type=pv.type)

        where = "pvname='%s'" % pv.pvname
        o = self.cache.select_one(where=where)
        if o['pvname'] not in self.pvnames:
            self.pvnames.append(o['pvname'])

    def read_alert_settings(self):
        for i in self._table_alerts.select():
            #  sys.stdout.write('PV ALERT %s\n' % repr(i['pvname']))
            pvname = i.pop('pvname')
            if pvname not in self.alert_data:
                self.alert_data[pvname] = i
            else:
                self.alert_data[pvname].update(i)
            if 'last_notice' not in self.alert_data[pvname]:
                self.alert_data[pvname]['last_notice'] = -1
            if 'last_value' not in self.alert_data[pvname]:
                self.alert_data[pvname]['last_value'] = None
        # sys.stdout.write("read %i alerts \n" % len(self.alert_data))
        sys.stdout.flush()

    def process_alerts(self, debug=False):
        # sys.stdout.write('processing alerts at %s\n' % time.ctime())
        msg = 'Alert sent for PV=%s / Label =%s at %s\n'
        # self.db.set_autocommit(1)
        for pvname, alarm in self.alert_data.items():
            value = alarm.get('last_value', None)
            last_notice = alarm.get('last_notice', -1)
            if value is not None and alarm['active'] == 'yes':
                if debug:
                    print 'Process Alert for ', pvname, last_notice, alarm['timeout']

                notify= (time.time() - last_notice) > alarm['timeout']
                ok, notified = self.check_alert(alarm['id'], value,
                                                sendmail=notify)
                if debug:
                    print 'Alert: val OK? ', ok, ' Notified? ', notified
                if notified:
                    self.alert_data[pvname]['last_notice'] = time.time()
                    self.alert_data[pvname]['last_value']  = None
                    sys.stdout.write(msg % (pvname, alarm['name'], time.ctime()))
                elif ok:
                    self.alert_data[pvname]['last_value']  = None

                if debug: print '  >>process_alert done ', self.alert_data[pvname]['last_notice']

        self.db.set_autocommit(0)
