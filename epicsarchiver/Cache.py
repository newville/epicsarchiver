#!/usr/bin/env python

import os
import re
import time
import sys
import smtplib
from decimal import Decimal
import numpy as np
from sqlalchemy import MetaData, create_engine, engine, text
from sqlalchemy.orm import sessionmaker

import epics

from .util import (clean_input, clean_string, normalize_pvname,
                   tformat, valid_pvname, clean_mail_message)

from .config import (dbuser, dbpass, dbhost, master_db,
                     mailserver, mailfrom, cgi_url)

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
    print(('Adding PVs listed in file ', fname))
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
        print((' Add PVs: [ %s ] ' % (' '.join(words))))

        if len(pairs) > 100:
            print('set a few pair scores...')
            for i in range(20):
                words = pairs.pop(0)
                cache.set_allpairs(words, score=10)

    print('Waiting for all pvs requested to be put in cache....')
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


def get_dbengine(dbname, server='sqlite', create=False,
                 user='', password='',  host='', port=None):
    """create database engine"""
    if server == 'sqlite':
        return create_engine('sqlite:///%s' % (dbname))
    elif server == 'mysql':
        conn_str= 'mysql+mysqldb://%s:%s@%s:%d/%s'
        if port is None:
            port = 3306
        return create_engine(conn_str % (user, password, host, port, dbname))

    elif server.startswith('p'):
        conn_str= 'postgresql://%s:%s@%s:%d/%s'
        if port is None:
            port = 5432
        return create_engine(conn_str % (user, password, host, port, dbname))

def None_or_one(result):
    """expect result (as from query.fetchall() to return 
    either None or exactly one result
    """
    if isinstance(result, engine.result.ResultProxy):
        return result
    try:
        return result[0]
    except:
        return None

class Cache(object):

    optokens = ('ne', 'eq', 'le', 'lt', 'ge', 'gt')
    opstrings= ('not equal to', 'equal to',
                'less than or equal to',    'less than',
                'greater than or equal to', 'greater than')
    ops = {'eq':'__eq__', 'ne':'__ne__', 
           'le':'__le__', 'lt':'__lt__', 
           'ge':'__ge__', 'gt':'__gt__'}

    def __init__(self, pidfile='/tmp/cache.pid', **kws):
        self.pidfile = pidfile
        t0 = time.monotonic() 
        self.engine = get_dbengine(master_db, server='mysql', user=dbuser,
                                   password=dbpass,  host=dbhost)
        self.metadata = MetaData(self.engine)
        self.metadata.reflect()
        self.conn    = self.engine.connect()
        self.session = sessionmaker(bind=self.engine, autocommit=True)()
        self.tables  = self.metadata.tables
        self.pid = self.get_pid()
        self.last_update = 0
        self.pvs   = {}
        self.data  = {}
        self.alert_data = {}

        for pvname in self.get_pvnames():
            self.pvs[pvname] = epics.get_pv(pvname)
        self.read_alert_table()
        print('created %d PVs , ready to run mainloop  %.3f sec' % (len(self.pvs), time.monotonic()-t0))

    def get_info(self, name='db', process='cache'):
        " get value from info table"
        table = self.tables['info']
        where = text("process='%s'" % process)
        return None_or_one(table.select(whereclause=where).execute().fetchall())

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
        self.session.flush()

    def get_pid(self):
        self.pid = self.get_info('pid', process='cache').pid
        return self.pid

    def get_pvnames(self):
        """ generate self.pvnames: a list of pvnames in the cache"""
        q = self.tables['cache'].select().execute()
        return [row.pvname for row in q.fetchall()]

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
        print("connect to pvs: %.3f sec, %d new entries" % (time.time()-t0, nnew))
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
        self.set_info(datetime=time.ctime(self.last_update), ts=self.last_update)

    def mainloop(self, npvs=None):
        " "
        sys.stdout.write('Starting Epics PV Archive Caching: \n')
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
        sys.stdout.write(fmt % (nconn, len(self.pvs), self.pid))

        for alert in self.alert_data.values():
            if alert['last_value'] is None and alert['pvname'] in self.pvs:
                pv = self.pvs[alert['pvname']]
                if pv.connected:
                    alert['last_value'] = pv.value

        print("Alerts: ")
        for name, alert in self.alert_data.items():
            print(name,  alert['last_value'], alert['trippoint'], alert['pvname'])
        
        status_str = '%s: %d values cached since last notice %d loops\n'
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
                    sys.stdout.write('no longer master, exiting\n\n')
                    sys.stdout.flush()
                    self.exit()
            # report and reconnect once ever 5 minutes
            if time.time() > last_report + 60:
                sys.stdout.write(status_str % (time.ctime(), ncached, nloop))
                sys.stdout.flush()
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
            sys.stdout.write('adding PV.....\n')
            return self.get_full(pvname, add=False)

        where = text("pvname='%s'" % pvname)
        table = self.tables['cache']
        out = None_or_one(table.select(whereclause=where).execute().fetchall())
        if out is None:
            out = {'value':None, 'ts':0, 'cvalue':None, 'type':None}
        return out

    def get(self, pvname, add=False, use_char=True):
        " return cached value of pv"
        ret = self.get_full(pvname, add=add)
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
                               'val': clean_string(val, maxlen=254),
                               'cval': clean_string(cval)}

        table = self.tables['cache']
        with self.session.begin():
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

    def set_value(self, pv):
        table = self.tables['cache']
        val = pv.value
        if isinstance(val, np.ndarray):
            val = val.tolist()
        vals = {table.c.ts: time.time(),
                table.c.value: clean_string(val, maxlen=254),
                table.c.cvalue: clean_string(pv.char_value)}
        table.update().where(table.c.pvname==pv.pvname).values(vals).execute()


    def add_epics_pv(self ,pv):
        """ add an epics PV to the cache"""
        if pv.pvname in self.pvs:
            return

        if not pv.connected:
            print('PV %s not connected' % repr(pv))
            return

        cval = pv.get(as_string=True)
        table = self.tables['cache']
        table.insert().execute(pvname=pv.pvname, type=pv.type)
        self.pvs[pvname] = pv
        self.data[pvname] = (pv.value, pv.char_value, time.time())
        pv.add_callback(self.onChanges)
        self.connect_pvs()

    def process_alerts(self, debug=False):
        # sys.stdout.write('processing alerts at %s\n' % time.ctime())
        msg = 'Alert sent for PV=%s / Label =%s at %s\n'
        # self.db.set_autocommit(1)
        table = self.tables['alerts']
        print(" Process alerts ")
        for pvname, alert in list(self.alert_data.items()):
            value = alert.get('last_value', None)
            if alert['active'] == 'no' or value is None:
                continue
            last_notice = alert.get('last_notice', -1)
            # if debug:
            #     print(('Process Alert for ', pvname, last_notice, alert['timeout']))
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
                print(('Alert: val OK? ', ok, ' Notified? ', notified))
            if notify:
                alert['last_notice'] = time.time()
                sys.stdout.write(msg % (pvname, alert['name'], time.ctime()))
            if value_ok or notify:
                alert['last_value']  = None

            if debug:
                print(('  >>process_alert done ', alert['last_notice']))

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
              (mailfrom,subject,'\n'.join(mlines),cgi_url,pvname)

        try:
            s = smtplib.SMTP(mailserver)
            # s.sendmail(mailfrom, mailto, msg)
            print("Would Send Mail ", msg)
            s.quit()
        except:
            sys.stdout.write("Could not send Alert mail:  mail not configured??")

    def process_requests(self):
        " process requests for new PV's to be cached"
        reqtable = self.tables['requests']
        req = reqtable.select().execute().fetchall()
        if len(req) == 0:
            return

        sys.stdout.write("processing requests:\n")
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
                        cache.update(cache.c.id==row.id).execute(active='no')
                        msg = 'suspended'
                elif 'drop' == action:
                    if pvname in self.pvs:
                        cache.delete().where(cache.c.id==row.id)
                        msg = 'dropped'
                elif 'add' == action:
                    if pvname not in self.pvs:
                        pv = epics.get_pv(pvname)
                        conn = pv.wait_for_connection(timeout=3.0)
                        if conn:
                            self.add_epics_pv(pv)
                            self.set_value(pv)
                            msg = 'added'
                        else:
                            msg = 'could not add'
                    else:
                        msg = 'already added'
            sys.stdout.write('%s PV: %s\n' % (msg, pvname))

        time.sleep(0.01)
        for rid in drop_ids:
            reqtable.delete().where(reqtable.c.id==rid)

        sys.stdout.flush()


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

