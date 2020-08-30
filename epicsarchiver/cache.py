#!/usr/bin/env python

import os
import re
import time
import sys
import logging
import smtplib
from decimal import Decimal

import numpy as np
from sqlalchemy import text
import epics

from .util import (clean_bytes, normalize_pvname, tformat, valid_pvname,
                   clean_mail_message, DatabaseConnection, None_or_one,
                   MAX_EPOCH, get_config, motor_fields)

logging.basicConfig(level=logging.INFO)

def add_pv(pvname, cache=None, with_motor_fields=True):
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
    n = cache.add_pv(pvname, with_motor_fields=with_motor_fields)


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
    loggin.debug('Adding PVs listed in file: %s ' % fname)
    with  open(fname,'r') as fh:
        lines = fh.readlines()

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
        logging.info("Adding PVs: [ %s ] " % (' '.join(words)))

        if len(pairs) > 100:
            for i in range(20):
                words = pairs.pop(0)
                cache.set_allpairs(words, score=10)

    logging.debug('Waiting for all pvs requested to be put in cache....')
    # now wait for all requests to be fulfilled, and then set the remaining pair scores

    req_table= cache.db.tables['requests']
    requests_pending = True

    while requests_pending:
        pending_requests  = req_table.select()
        requests_pending = len(pending_requests) > 2
        time.sleep(1)

    logging.debug('Finally, set remaining of pair scores:')
    while pairs:
        words = pairs.pop(0)
        cache.set_allpairs(words,score=10)
    cache.close()

    time.sleep(0.01)
    epics.poll(evt=0.01,iot=5.0)


class Cache(object):
    optokens = ('ne', 'eq', 'le', 'lt', 'ge', 'gt')
    opstrings= ('not equal to', 'equal to',
                'less than or equal to',    'less than',
                'greater than or equal to', 'greater than')
    ops = {'eq':'__eq__', 'ne':'__ne__', 
           'le':'__le__', 'lt':'__lt__', 
           'ge':'__ge__', 'gt':'__gt__'}

    def __init__(self, envvar='PVARCH_CONFIG', **kws):
        self.config = get_config(envar=envvar, **kws)
        
        self.pidfile = os.path.join(self.config.logdir,  'pvcache.pid')
        t0 = time.monotonic() 
        self.db = DatabaseConnection(self.config.master_db, self.config)
        self.tables  = self.db.tables
        # self.check_for_updates()
        self.pid = self.get_pid()
        self.last_update = 0
        self.pvs   = {}
        self.data  = {}
        self.alert_data = {}
        self.get_pvnames()
        self.read_alert_table()
        logging.info('created %d PVs %.3f sec' % (len(self.pvs), time.monotonic()-t0))

    def check_for_updates(self):
        """
        check db version and maybe repair datatypes or otherwise check and alter tables
        """
        version_row = self.get_info(process='version')
        print(" VERSION ROW ", version_row)
        if version_row is None:
            logging.info("upgrading database to version 1")
            for stmt in  ("alter table info modify process varchar(256);",
                          "alter table cache modify value varchar(4096);",
                          "alter table cache modify cvalue varchar(4096);",
                          "alter table pairs modify pv1 varchar(128);",
                          "alter table pairs modify pv2 varchar(128);",
                          "update cache set type='double' where type='time_double';",
                          "update cache set type='double' where type='time_float';",
                          "update cache set type='double' where type='float';",
                          "update cache set type='string' where type='time_string';",
                          "update cache set type='string' where type='time_char';",
                          "update cache set type='string' where type='char';",
                          "update cache set type='enum' where type='time_enum';",
                          "update cache set type='int' where type='time_int';",
                          "update cache set type='int' where type='time_long';",
                          "update cache set type='int' where type='time_short';",
                          "update cache set type='int' where type='long';",
                          "update cache set type='int' where type='short';"):
                self.db.engine.execute(stmt)
            now = time.time()                
            self.tables['info'].insert().execute(process='version', db='1',
                                                 datetime=tformat(now), ts=now)
            time.sleep(0.25)            
            self.db = DatabaseConnection(self.config.master_db, self.config)
            
        
    def get_info(self, process='cache'):
        " get value from info table"
        info = self.tables['info']
        return None_or_one(info.select().where(info.c.process==process).execute().fetchall())

    def set_info(self, process='cache', **kws):
        " set value(s) in the info table"
        table = self.tables['info']
        where = text("process='%s'" % process)

        q = table.update().where(table.c.process==process)
        vals = {}
        for key, val in kws.items():
            k = getattr(table.c, key, None)
            if k is not None:
                vals[k] = val
        q.values(vals).execute()
        self.db.flush()

    def get_pid(self):
        self.pid = self.get_info(process='cache').pid
        return self.pid

    def get_pvnames(self):
        """ generate self.pvnames: a list of pvnames in the cache"""
        for row in self.tables['cache'].select().execute().fetchall():
            if row.pvname not in self.pvs:
                self.pvs[row.pvname] = epics.get_pv(row.pvname)
        return self.pvs.keys()

    def status_report(self, brief=False, dt=60):
        # return self.cache_report(brief=brief,dt=dt)
        out = []
        pid = self.get_pid()
        table = self.tables['cache']
        where = text("ts>'%d'" % int(time.time()-dt))
        q = table.select(whereclause=where).order_by(table.c.ts).execute()
        ret= q.fetchall()
        fmt = " %s  %.35s   %s"
        if not brief:
            for r in ret:
                out.append(fmt % (tformat(t=float(r.ts),format="%H:%M:%S"),
                                  r.pvname +' '*35, r.value.decode('utf-8')))

        fmt = '%d of %d PVs had values updated in the past %.1f seconds. pid=%d'
        out.append(fmt % (len(ret), len(self.pvs), dt, pid))
        return '\n'.join(out)

    def connect_pvs(self):
        """connect to unconnected PVs, make sure callback is defined"""
        nnew = 0
        t0 = time.time()
        for pvname, pv in self.pvs.items():
            if pv.connected:
                cval = pv.get(as_string=True)
                if len(pv.callbacks) < 1:
                    nnew += 1
                    pv.add_callback(self.onChanges)
                    self.data[pvname] = (pv.value, cval, time.time())
                    if pvname in self.alert_data:
                        self.alert_data[pvname]['last_value'] = pv.value
                        self.alert_data[pvname]['last_notice'] = time.time() - 30.0
        logging.info("connect to pvs: %.3f sec, %d new entries" % (time.time()-t0, nnew))
        return nnew

    def onChanges(self, pvname=None, value=None, char_value=None,
                  timestamp=None, **kw):
        if value is not None and pvname is not None:
            if timestamp is None:
                timestamp = time.time()
            self.data[pvname] = (value, char_value, timestamp)
            if pvname in self.alert_data:
                self.alert_data[pvname]['last_value'] = value

    def set_date(self):
        self.last_update = time.time()
        self.set_info(datetime=tformat(self.last_update), ts=self.last_update)

    def mainloop(self, npvs=None):
        " "
        logging.info('Starting Epics PV Archive Caching:')
        t0 = time.time()
        self.pid = os.getpid()
        self.set_info(status='running', pid=self.pid)
        self.set_date()

        fout = open(self.pidfile, 'w')
        fout.write('%i\n' % self.pid)
        fout.close()

        # self.db.get_cursor()
        nconn = self.connect_pvs()
        fmt = '%d/%d pvs connected, ready to run. Cache Process ID= %i\n'
        logging.info(fmt % (nconn, len(self.pvs), self.pid))

        for alert in self.alert_data.values():
            if alert['last_value'] is None and alert['pvname'] in self.pvs:
                pv = self.pvs[alert['pvname']]
                if pv.connected:
                    alert['last_value'] = pv.value

        for name, alert in self.alert_data.items():
            logging.debug('Add Alert: %s / %s' % (name,  alert['pvname']))
        
        status_str = '%s: %d values cached since last notice %d loops'
        ncached, nloop = 0, 0
        last_report = 0
        last_request_process = 0
        while True:
            try:
                epics.poll(evt=0.02, iot=1.0)
                n = self.update_cache()
            except KeyboardInterrupt:
                break
            ncached +=  n
            nloop   +=  1

            # process alerts every 15 seconds:
            if (time.time() > last_request_process + 15):
                self.process_requests()
                self.process_alerts()
                last_request_process = time.time()
                if self.get_pid() != self.pid:
                    logging.debug('no longer main cache program, exiting\n\n')
                    self.exit()
            # report and reconnect once ever 5 minutes
            if time.time() > last_report + 60:
                logging.info(status_str % (time.ctime(), ncached, nloop))
                last_report = time.time()
                self.read_alert_table()
                self.connect_pvs()
                ncached = 0
                nloop = 0


    def exit(self):
        self.close()
        for i in list(self.pvs.values()):
            i.disconnect()
        sys.exit()

    def shutdown(self):
        self.set_cache_pid(0)
        self.exit()

    def get_full(self, pvname, add=False):
        " return full information for a cached pv"
        pvname = normalize_pvname(pvname)
        self.get_pvnames()
        if add and pvname not in self.pvs:
            self.add_pv(pvname)
            logging.debug('adding PV  %s ' % pvname)
            time.sleep(0.1)
            return self.get_full(pvname, add=False)

        where = text("pvname='%s'" % pvname)
        table = self.tables['cache']
        out = None_or_one(table.select(whereclause=where).execute().fetchall())
        return out

    def get(self, pvname, add=False, use_char=True):
        " return cached value of pv"
        ret = self.get_full(pvname, add=add)
        if ret is None:
            return None
        if use_char:
            return ret['cvalue']
        return ret['value']

    def update_cache(self):
        # take new pvnames as of right now, and pop off the latest
        # values for these pvs.
        # Note: be careful to not set self.data = {}, which would
        # blow away any changes that occur during this processing
        newdata = {}
        for pvname in list(self.data.keys()):
            val, cval, tstamp = self.data.pop(pvname)
            if isinstance(val, np.ndarray):
                val = val.tolist()
            newdata[pvname] = {'ts': tstamp,
                               'val': clean_bytes(val),
                               'cval': clean_bytes(cval)}

        table = self.tables['cache']
        with self.db.session.begin():
            for pvname, dat in newdata.items():
                row = table.update().where(table.c.pvname==pvname)
                row.values({table.c.ts: dat['ts'],
                            table.c.value: dat['val'],
                            table.c.cvalue: dat['cval']}).execute()
        self.set_date()
        return len(newdata)

    def get_values(self, all=False, time_ago=60.0):
        table = self.tables['cache']
        query = table.select()
        if not all:
            query = query.where(table.c.ts>Decimal(time.time() - time_ago))
        return query.execute().fetchall()


    def add_pv(self, pvname, with_motor_fields=True):
        """ add a PV or list of PVs to the cache"""
        if isinstance(pvname, (str, bytes)):
            pvname = [pvname]

        pvs, nadded = [], 0
        for name in  pvname:
            if isinstance(name, bytes):
                name = name.decode('utf-8')
            if name not in self.pvs:
                pvs.append(epics.get_pv(pvname))
                
        if len(pvs) == 0:
            return

        addcmd = self.tables['cache'].insert().execute
        def add_pv2cache(pv):
            self.pvs[pv.pvname] = pv
            pvtype = pv.type.replace('ctrl_', '').replace('time_', '')
            pvtype = pvtype.replace('short', 'int').replace('long', 'int')
            pvtype = pvtype.replace('float', 'double')
            cval = pv.get(as_string=True)
            val = pv.value
            if isinstance(val, np.ndarray):
                val = val.tolist()
            addcmd(pvname=pvname,
                   type=pvtype,
                   ts=time.time(),
                   value=clean_bytes(val, maxlen=4096),
                   cvalue=clean_bytes(cval, maxlen=4096),
                   active='yes')
            nadded += 1
                    
        time.sleep(0.010)
        for pv in pvs:
            if pv.wait_for_connection(timeout=3.0):
                add_pv2cache(pv)
                extra_pvs = []
                prefix = pv.pvname
                if prefix.endswith('.VAL'): prefix = prefix[:-4]
                if '.' in prefix or pvtype != 'double':
                    continue
                rtype = epics.get_pv(prefix+'.RTYP')
                if 'motor' != rtype.get():
                    continue
                namelist = ["%s%s" % (prefix, i) for i in motor_fields]
                extra_pvs = [epics.get_pv(n) for n in namelist]
                namelist.append(pv.pvname)
                for epv in extra_pvs:
                    if pv.wait_for_connection(timeout=1):
                        add_pv2cache(pv)
                        self.set_allpairs(epv, namelist, score=10)
        self.connect_pvs()
        return nadded

    def drop_pv(self, pvname):
        """ request that a PV (by name) be dropped from the cache"""
        table = self.tables['requests']
        table.insert().execute(pvname=pv.pvname, action='drop', ts=time.time())

        if pvname in self.pvs():
            thispv = self.pvs.pop(pvname)
            thispv.clear_callbacks()
        if pvname in self.data:
            self.data.pop(pvname)

    def process_alerts(self, debug=False):
        logging.debug('processing alerts at %s\n' % time.ctime())
        msg = 'Alert sent for PV=%s / Label =%s at %s\n'
        # self.db.set_autocommit(1)
        table = self.tables['alerts']
        for pvname, alert in list(self.alert_data.items()):
            value = alert.get('last_value', None)
            if alert['active'] == 'no' or value is None:
                continue
            last_notice = alert.get('last_notice', -1)
            notify= (time.time() - last_notice) > alert['timeout']

            # coerce values to strings or floats for comparisons
            convert = str
            if isinstance(value,(int, float)):
                convert = float

            value     = convert(value)
            trippoint = convert(alert['trippoint'])
            cmp       = self.ops[alert['compare']]

            # compute new alarm status: note form  'value.__ne__(trippoint)'
            value_ok = not getattr(value, cmp)(trippoint)

            old_value_ok = (alert['status'] == 'ok')
            notify = notify and old_value_ok and (not value_ok)
            if old_value_ok != value_ok:
                # update the status field in the alerts table
                status = 'alarm'
                if value_ok:
                    status = 'ok'
                table.update(whereclause=text("pvname='%s'" %  pvname)).execute(status=status)
                if notify:
                    self.send_alert_mail(alert, value)

            if debug:
                logging.debug('Alert: val OK? %r Notified" %r' % ( ok, notified))
            if notify:
                alert['last_notice'] = time.time()
                logging.debug(msg % (pvname, alert['name'], time.ctime()))
            if value_ok or notify:
                alert['last_value']  = None

            if debug:
                logging.debug('  >>process_alert done %s' %  alert['last_notice'])

    def send_alert_mail(self, alert, value):
        """ send an alert email from an alert dict holding
        the appropriate row of the alert table.        
        """
        mailto = alert['mailto']
        pvname = alert['pvname']
        label  = alert['name']
        compare= alert['compare']
        msg    = alert['mailmsg']

        if mailto in ('', None) or pvname in ('', None):
            return

        mailto = mailto.replace('\r','').replace('\n','')

        trippoint = str(alert['trippoint'])
        mailto    = tuple(mailto.split(','))
        subject   = "[Epics Alert] %s" % (label)

        if msg in ('', None):
            msg = self.def_alert_msg

        msg  = clean_mail_message(msg)

        opstr = 'not equal to'
        for tok,desc in zip(self.optokens, self.opstrings):
            if tok == compare: opstr = desc

        # fill in 'template' values in mail message
        for k, v in list({'PV': pvname,  'LABEL':label,
                          'COMP': opstr, 'VALUE': str(value),  
                          'TRIP': str(trippoint)}.items()):
            msg = msg.replace("%%%s%%" % k, v)

        # do %PV(XX)% replacements
        re_showpv = re.compile(r".*%PV\((.*)\)%.*").match
        mlines = msg.split('\n')

        for i,line in enumerate(mlines):
            nmatch = 0
            match = re_showpv(line)
            while match is not None and nmatch<25:
                pvn = match.groups()[0]
                line = line.replace('%%PV(%s)%%' % pvn, self.get(pvn))
                # except:
                #     line = line.replace('%%PV(%s)%%' % pvn, 'Unknown_PV(%s)' % pvn)
                match = re_showpv(line)
                nmatch = nmatch + 1
            mlines[i] = line
        msg = "From: %s\r\nSubject: %s\r\n%s\nSee %s/plot/%s\n" % \
              (self.config.mail_from, subject,'\n'.join(mlines),
               self.config.baseurl, pvname)

        try:
            s = smtplib.SMTP(self.config.mail_server)
            # s.sendmail(self.config.mail_from, mailto, msg)
            logging.info("Would Send Mail : %s" % msg)
            s.quit()
        except:
            logging.warning("Could not send Alert mail:  mail not configured??")

    def process_requests(self):
        " process requests for new PV's to be cached"
        reqtable = self.tables['requests']
        req = reqtable.select().execute().fetchall()
        if len(req) == 0:
            return

        logging.info("processing requests:\n")
        cache = self.tables['cache']
        drop_ids = []
        for row in req:
            pvname, action = row.pvname, row.action
            msg = 'could not process request for'
            drop_ids.append(row.id)
            if valid_pvname(pvname):
                if 'suspend' == action:
                    if pvname in self.pvs:
                        self.pvs[pvname].clear_callbacks()
                        cache.update().where(cache.c.pvname==pvname).values({'active': 'no'})
                        msg = 'suspended'
                elif 'drop' == action:
                    if pvname in self.pvs:
                        cache.delete().where(cache.c.pvname==pvname)
                        msg = 'dropped'
                elif 'add' == action:
                    self.add_pv(pvname)
                    
                    if pvname not in self.pvs:
                        pv = epics.get_pv(pvname)
                        conn = pv.wait_for_connection(timeout=3.0)
                        if conn:
                            needs_connect_pvs = True
                            self.pvs[pv.pvname] = pv
                            cval = pv.get(as_string=True)
                            val = pv.value
                            if isinstance(val, np.ndarray):
                                val = val.tolist()
                            cache.insert().execute(pvname=pvname, type=pv.type,
                                                   ts=time.time(),
                                                   value=clean_bytes(val, maxlen=4096),
                                                   cvalue=clean_bytes(cval, maxlen=4096),
                                                   active='yes')
                            msg = 'added'
                        else:
                            msg = 'could not add'
                    else:
                        msg = 'already added'
            logging.debug('%s PV: %s\n' % (msg, pvname))

        time.sleep(0.01)
        for rid in drop_ids:
            reqtable.delete().where(reqtable.c.id==rid)

            
            
    def read_alert_table(self):
        for alert in self.tables['alerts'].select().execute().fetchall():
            pvname = alert.pvname
            if pvname not in self.alert_data:
                self.alert_data[pvname] = dict(alert)
            else:
                self.alert_data[pvname].update(dict(alert))
            if 'last_notice' not in self.alert_data[pvname]:
                self.alert_data[pvname]['last_notice'] = 0
            if 'last_value' not in self.alert_data[pvname]:
                value = None
                if pvname in self.pvs:
                    value = self.pvs[pvname].value
                self.alert_data[pvname]['last_value'] = value


    def get_runs(self, start_time=0, stop_time=None):
        runs = self.tables['runs']
        if stop_time is None:
            stop_time = MAX_EPOCH
        q = runs.select().where(runs.c.start_time <= Decimal(stop_time))
        q = q.where(runs.c.stop_time >= Decimal(start_time))
        return q.execute().fetchall()
    
            
