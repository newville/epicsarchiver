#!/usr/bin/env python

import os
import re
import time
import sys
import logging
import smtplib
from decimal import Decimal

import numpy as np
from sqlalchemy import text, and_
import epics

from .util import (clean_bytes, normalize_pvname, tformat, valid_pvname,
                   clean_mail_message, DatabaseConnection, None_or_one,
                   MAX_EPOCH, get_config, motor_fields, get_pvpair)

from . import schema

logging.basicConfig(level=logging.INFO,
                    format='%(levelname)s [%(asctime)s]  %(message)s',
                    datefmt='%Y-%b-%d %H:%M:%S')

STAT_MSG = "{process:8s} {status:8s}, pid={pid:7d}, {n_new:5d} values {action:8s} in past {time:2d} seconds [{datetime:s}]"

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
    logger.debug('Adding PVs listed in file: %s ' % fname)
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

    def __init__(self, envvar='PVARCH_CONFIG', pvconnect=True, debug=False, **kws):
        t0 = time.monotonic()
        self.config = get_config(envar=envvar, **kws)
        self.pvconnect = pvconnect
        self.logger = logging.getLogger()
        if debug:
            self.logger.setLevel(logging.DEBUG)
        self.log_writers = {'info': self.logger.info,
                            'debug': self.logger.debug,
                            'warn': self.logger.warn,
                            'warning': self.logger.warn,
                            'error': self.logger.error,
                            'critical': self.logger.critical}
        self.pidfile = os.path.join(self.config.logdir,  'pvcache.pid')
        self.db = DatabaseConnection(self.config.cache_db, self.config)
        self.tables  = self.db.tables
        self.pid, _status = self.get_pidstatus()

        self.check_for_updates()
        self.pvs   = {}
        self.data  = {}
        self.alert_data = {}
        self.get_pvnames()
        self.read_alert_table()
        if self.pvconnect:
            self.log('cache with %d PVs ready, %.3f sec' % (len(self.pvs),
                                                            time.monotonic()-t0))

    def log(self, message, level='info'):
        writer = self.log_writers.get(level, self.logger.info)
        writer(message)


    def check_for_updates(self):
        """
        check db version and maybe repair datatypes or otherwise check and alter tables
        """
        version_row = self.get_info(process='version')
        if version_row is None:
            self.log("upgrading database to version 1")
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
            self.db = DatabaseConnection(self.config.cache_db, self.config)


    def create_next_archive(self, copy_pvs=True):
        """Create a pvdata database for archiving

        This checks carefully for the case of "no archive yet".
        """
        conf = self.config
        arch_row = self.get_info(process='archive')
        current_dbname = None
        current_index = 0
        if arch_row is not None:
            current_dbname = arch_row.db
            numstr = current_dbname.replace(conf.dat_prefix, '')
            numstr = numstr.replace('_', '').replace('-', '')
            try:
                current_index = int(numstr)
            except:
                raise ValueError('cannot get index of current database: %s' % current_dbname)

        dbname = conf.dat_format % (conf.dat_prefix, current_index+1)

        sql = ['create database {dbname:s}; use {dbname:s};'.format(dbname=dbname),
               schema.pvdat_init_pv]
        for idat in range(1, 129):
            sql.append(schema.pvdat_init_dat.format(idat=idat))

        self.log("creating database %s" % dbname)
        self.db.engine.execute('\n'.join(sql))
        self.db.flush()
        time.sleep(0.5)
        if copy_pvs and current_dbname is not None:
            print("copy pvs from ", current_dbname)
            archdb = DatabaseConnection(current_dbname, self.config)
            nextdb = DatabaseConnection(dbname, self.config)

            add2next = nextdb.tables['pv'].insert()
            for pvdata in archdb.tables['pv'].select().execute().fetchall():
                add2next.execute(name=pvdata.name,
                                 description=pvdata.description,
                                 type=pvdata.type,
                                 data_table=pvdata.data_table,
                                 deadtime=pvdata.deadtime,
                                 deadband=pvdata.deadband,
                                 graph_lo=pvdata.graph_lo,
                                 graph_hi=pvdata.graph_hi,
                                 graph_type=pvdata.graph_type,
                                 active=pvdata.active)

        return dbname


    def get_info(self, process='cache'):
        " get value from info table"
        info = self.tables['info']
        return None_or_one(info.select().where(info.c.process==process).execute().fetchall())

    def get_pidstatus(self, process='cache'):
        row = self.get_info(process=process)
        return row.pid, row.status

    def set_info(self, process='cache', **kws):
        " set value(s) in the info table"
        table = self.tables['info']
        table.update().where(table.c.process==process).execute(**kws)
        self.db.flush()

    def get_pvnames(self):
        """ generate self.pvnames: a list of pvnames in the cache"""
        pvnames = []
        for row in self.tables['cache'].select().execute().fetchall():
            pvnames.append(row.pvname)
            if row.pvname not in self.pvs and self.pvconnect:
                self.pvs[row.pvname] = epics.get_pv(row.pvname)
        return pvnames

    def get_narchived(self, time_ago=60):
        """
        return the number of values archived by the archive in the past N seconds.
        if limit is set, return as  soon as this limit is seen to be exceeded
        this is useful when checking if any values have been cached.
        """
        n = 0
        archdbname = self.get_info(process='archive').db
        archdb = DatabaseConnection(archdbname, self.config)

        whereclause = text("time>%d" % (time.time()-time_ago))
        for i in range(1, 129):
            q = archdb.tables['pvdat%3.3d' % i].select(whereclause=whereclause)
            n += len(q.execute().fetchall())
        return n

    def show_status(self, with_archive=True, cache_time=60, archive_time=60):
        info = dict(self.get_info(process='cache').items())
        info.update({'n_new': len(self.get_values(time_ago=cache_time)),
                     'time': cache_time,
                     'process': 'Cache', 'action': 'updated'})

        print(STAT_MSG.format(**info))
        if with_archive:
            info = dict(self.get_info(process='archive').items())
            info.update({'n_new': self.get_narchived(time_ago=archive_time),
                         'time': archive_time,
                         'process': 'Archiver', 'action': 'archived'})
            print(STAT_MSG.format(**info))

    def set_runinfo(self, dbname=None):
        """set timerange for an archive run"""
        tmin = MAX_EPOCH
        tmax = 0
        current_dbname = self.get_info(process='archive').db
        if dbname is None:
            dbname = current_dbname
        if dbname == current_dbname:
            tmax = MAX_EPOCH
        archdb = DatabaseConnection(dbname, self.config)
        for i in range(1, 129):
            tab = archdb.tables['pvdat%3.3d' % i]
            oldest = tab.select().order_by(tab.c.time)
            newest = tab.select().order_by(tab.c.time.desc())
            tmin = min(tmin, float(oldest.limit(1).execute().fetchone().time))
            tmax = max(tmax, float(newest.limit(1).execute().fetchone().time))

        notes = "%s to %s" % (tformat(tmin), tformat(tmax))
        runs = self.tables['runs']
        logging.info(("set run info for %s: %s" %  (dbname, notes)))
        runs.update().where(runs.c.db==dbname).execute(notes=notes,
                                                       start_time=tmin,
                                                       stop_time=tmax)


    def connect_pvs(self):
        """connect to unconnected PVs, make sure callback is defined"""
        nnew = 0
        if not self.pvconnect:
            return 0
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
        self.log("connect to pvs: %.3f sec, %d new entries" % (time.time()-t0, nnew))
        return nnew

    def onChanges(self, pvname=None, value=None, char_value=None,
                  timestamp=None, **kw):
        if value is not None and pvname is not None:
            if timestamp is None:
                timestamp = time.time()
            self.data[pvname] = (value, char_value, timestamp)
            if pvname in self.alert_data:
                self.alert_data[pvname]['last_value'] = value

    def mainloop(self, npvs=None):
        "main loop"
        if not self.pvconnect:
            raise ValueError('cannot run mainloop with pvconnect=False')

        self.pid = os.getpid()
        self.log('Starting Epics PV Caching: pid = %d' % self.pid)
        t0 = time.time()
        self.set_info(process='cache', status='running', pid=self.pid, ts=t0,
                      datetime=tformat(t0))

        fout = open(self.pidfile, 'w')
        fout.write('%i\n' % self.pid)
        fout.close()

        # self.db.get_cursor()
        nconn = self.connect_pvs()
        fmt = '%d/%d pvs connected, ready to run. Cache Process ID= %d'
        self.log(fmt % (nconn, len(self.pvs), self.pid))

        for alert in self.alert_data.values():
            if alert['last_value'] is None and alert['pvname'] in self.pvs:
                pv = self.pvs[alert['pvname']]
                if pv.connected:
                    alert['last_value'] = pv.value

        for name, alert in self.alert_data.items():
            self.log('Add Alert: %s / %s' % (name,  alert['pvname']), level='debug')

        status_str = '%d values cached since last notice %d loops'
        ncached, nloop = 0, 0
        last_report = last_info = last_request_process = 0
        collecting = True
        while collecting:
            try:
                epics.poll(evt=0.003, iot=1.0)
                n = self.update_cache()
            except KeyboardInterrupt:
                self.log('Interrupted by user.', level='warn')
                self.set_info(process='info', status='offline')
                collecting = False
                break
            ncached +=  n
            nloop   +=  1

            tnow = time.time()
            if tnow > last_info + 2.0:
                self.set_info(process='cache', ts=tnow, datetime=tformat(tnow))
                last_info = tnow
                pid, status = self.get_pidstatus()
                if status in ('stopping', 'offline') or  pid != self.pid:
                    self.log('no longer main cache program, exiting.')
                    collecting = False
                    last_report = last_request = time.time() + 1
            # process alerts every 15 seconds:
            if time.time() > last_request_process + float(self.config.cache_alert_period):
                self.process_requests()
                self.process_alerts()
                last_request_process = time.time()
            # report and reconnect once ever 5 minutes
            if tnow > last_report + float(self.config.cache_report_period):
                self.log(status_str % (ncached, nloop))
                last_report = tnow
                self.read_alert_table()
                self.connect_pvs()
                ncached = 0
                nloop = 0
        self.set_info(process='cache', status='offline')
        time.sleep(1)

    def shutdown(self):
        self.set_info(process='cache', status='stopping')

    def get_full(self, pvname, add=False):
        " return full information for a cached pv"
        pvname = normalize_pvname(pvname)
        self.get_pvnames()
        if add and self.pvconnect and pvname not in self.pvs:
            self.add_pv(pvname)
            self.log('adding PV  %s ' % pvname, level='debug')
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
        return len(newdata)

    def get_values(self, all=False, time_ago=60.0, time_order=False):
        table = self.tables['cache']
        query = table.select()
        if not all:
            query = query.where(table.c.ts>Decimal(time.time() - time_ago))
        if time_order:
            query = query.order_by(table.c.ts)
        return query.execute().fetchall()


    def add_pv(self, pvname, with_motor_fields=True):
        """ add a PV or list of PVs to the cache"""
        if isinstance(pvname, (str, bytes)):
            pvname = [pvname]

        pvs = []
        pvnames = self.get_pvnames()
        for name in  pvname:
            if isinstance(name, bytes):
                name = name.decode('utf-8')
            if name not in pvnames:
                pvs.append(epics.get_pv(name))

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
            return pvtype

        time.sleep(0.010)
        for pv in pvs:
            if pv.wait_for_connection(timeout=3.0):
                pvtype = add_pv2cache(pv)
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
        return

    def drop_pv(self, pvname):
        """ request that a PV (by name) be dropped from the cache"""
        table = self.tables['requests']
        table.insert().execute(pvname=pvname, action='drop', ts=time.time())

        if pvname in self.pvs:
            thispv = self.pvs.pop(pvname)
            thispv.clear_callbacks()
        if pvname in self.data:
            self.data.pop(pvname)

    def process_alerts(self, debug=False):
        self.log('processing alerts')
        msg = 'Alert sent for PV=%s, Label=%s'
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

            if notify:
                alert['last_notice'] = time.time()
                self.log(msg % (pvname, alert['name']), level='debug')
            if value_ok or notify:
                alert['last_value']  = None

            self.log('  >>process_alert done %s' %  alert['last_notice'],
                     level='debug')

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
            self.log("Would Send Mail : %s" % msg)
            s.quit()
        except:
            self.log("Could not send Alert mail:  mail not configured??",
                     level='warn')

    def process_requests(self):
        " process requests for new PV's to be cached"
        reqtable = self.tables['requests']
        req = reqtable.select().execute().fetchall()
        if len(req) == 0:
            self.log("no requests to process")
            return

        self.log("processing %d requests" % len(req) )
        cache = self.tables['cache']
        drop_ids = []
        for row in req:
            pvname, action = row.pvname, row.action
            msg = 'could not process request for'
            if valid_pvname(pvname):
                if 'suspend' == action:
                    if pvname in self.pvs:
                        self.pvs[pvname].clear_callbacks()
                        cache.update().where(cache.c.pvname==pvname).values(
                            {'active': 'no'}).execute()
                        reqtable.delete().where(reqtable.c.id==row.id).execute()
                        msg = 'suspended'
                elif 'drop' == action:
                    cache.delete().where(cache.c.pvname==pvname).execute()
                    reqtable.delete().where(reqtable.c.id==row.id).execute()
                    if pvname in self.pvs:
                        self.pvs[pvname].clear_callbacks()
                        self.pvs.pop(pvname)
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
                            reqtable.delete().where(reqtable.c.id==row.id).execute()
                            msg = 'added'
                        else:
                            msg = 'could not add'
                    else:
                        msg = 'already added'
            self.log('%s PV: %s' % (msg, pvname))
        time.sleep(0.01)


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


    def get_pair_score(self, pv1, pv2):
        "get pair score for 2 pvs"
        pv1, pv2 = get_pvpair(pv1, pv2)
        if pv1 not in self.pvs or pv2 not in self.pvs:
            return 0
        score = 0
        ptable = self.tables['pairs']
        for (a, b) in ((pv1, pv2), (pv2, pv1)):
            q = ptable.select().where(and_(ptable.c.pv1==a, ptable.c.pv2==b))
            r = None_or_one(q.execute().fetchall())
            if r is not None:
                score += r.score
        return score

    def set_pair_score(self, pv1, pv2, score=None, increment=1):
        "set pair score for 2 pvs"
        pv1, pv2 = get_pvpair(pv1, pv2)
        if pv1 not in self.pvs or pv2 not in self.pvs:
            self.log("Cannot set pair score for unknonwn PVS '%s' and '%s'" % (pv1, pv2),
                     level='warn')

        current_score = self.get_pair_score(pv1, pv2)
        if score is None:
            score = incremenet + current_score

        ptable = self.tables['pairs']
        if current_score == 0:
            ptable.insert().execute(pv1=pv2, pv2=pv2, score=score)
        else:
            ptable.update().execute(pv1=pv2, pv2=pv2, score=score)


    def increment_pair_score(self, pv1, pv2, increment=1):
        """increase by the pair score for two pvs """
        self.set_pair_score(pv1, pv2, score=None, increment=increment)

    def set_allpairs(self, pvlist, score=10):
        """for a list/tuple of pvs, set all pair scores
        to be at least the provided score"""
        tmplist = [normalize_pvname(p) for p in pvlist]
        self.get_pvnames()

        while tmplist:
            a = tmplist.pop()
            for b in tmplist:
                if self.get_pair_score(a, b) < score:
                    self.set_pair_score(a, b, score=score)


    def check_pairscores(self):
        "return all pair scores, logging duplicates"
        pairscores = {}
        ptable = self.tables['pairs']
        for row in ptable.select().execute().fetchall():
            pv1, pv2 = get_pvpair(row.pv1, row.pv2)
            key = '%s@%s' % (pv1, pv2)
            alt = '%s@%s' % (pv2, pv1)
            if key in pairscores or ald in pairscores:
                self.log('duplicate score found: %s / %s'%(pv1, pv2),
                         level='warn')
                pairscores[key] += row.score
            else:
                pairscores[key] = row.score
        return pairscores
