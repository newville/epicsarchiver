#!/usr/bin/env python
"""
Cache class for interacting with main database and cache table
"""
import os
import re
import json
import time
import logging
from smtplib import SMTP
from decimal import Decimal
from datetime import datetime

import psutil
import numpy as np
from sqlalchemy.orm import Session
from epics import get_pv
from tabulate import tabulate
from .util import (clean_bytes, normalize_pvname, tformat, valid_pvname,
                   clean_mail_message, DatabaseConnection, MAX_EPOCH,
                   get_config, motor_fields, hformat, row2dict)

from . import schema

logging.basicConfig(level=logging.INFO,
                    format='%(levelname)s [%(asctime)s]  %(message)s',
                    datefmt='%Y-%b-%d %H:%M:%S')
OPTOKENS = ('ne', 'eq', 'le', 'lt', 'ge', 'gt')
OPSTRINGS = ('not equal to', 'equal to', 'less than or equal to',
             'less than', 'greater than or equal to', 'greater than')

OPS = {'eq':'__eq__', 'ne':'__ne__',  'le':'__le__',
       'lt':'__lt__', 'ge':'__ge__', 'gt':'__gt__'}

class Cache:
    """interface to main/master pvarch database,
    used for running the caching process and for
    maintenance methods
    """
    def __init__(self, envvar='EPICSARCH_CONFIG',
                 debug=False, pvconnect=True, **kws):
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

        self.pvs   = {}
        self.data  = {}
        self.pvtypes = {}
        pvnames = self.get_pvnames()
        time.sleep(0.01)
        self.read_alert_table()
        self.init_time = time.monotonic() - t0
        if pvconnect:
            self.connect_pvs()
            connected = [p for p in self.pvs.values() if p.connected]
            self.log(f"Cache: {len(pvnames)} PVs, ({len(connected)} connected) ({self.init_time:.2f}s)")
        else:
            self.log(f"Cache: {len(pvnames)} PVs, (not connected) ({self.init_time:.2f}s)")

    def log(self, message, level='info'):
        writer = self.log_writers.get(level, self.logger.info)
        writer(message)


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
            except ValueError:
                raise ValueError(f'cannot database index: {current_dbname}')

        dbname = conf.dat_format % (conf.dat_prefix, current_index+1)
        self.log(f"creating database {dbname}")
        for sql_cmd in (f"drop database if exists {dbname:s};",
                        f"create database {dbname:s};",
                        f"use {dbname:s};",
                        schema.pvdat_init_pv ):
            self.db.sql_execute(sql_cmd)
        for idat in range(1, 129):
            self.db.sql_execute(schema.pvdat_init_dat.format(idat=idat))

        time.sleep(0.25)
        if copy_pvs and current_dbname is not None:
            print("copy pvs from ", current_dbname)
            archdb = DatabaseConnection(current_dbname, self.config)
            nextdb = DatabaseConnection(dbname, self.config)

            cur_pvdat = archdb.execute(archdb.tables['pv'].select()).fetchall()

            npv_insert = nextdb.tables['pv'].insert()
            for pvdata in cur_pvdat:
                q = npv_insert.values(name=pvdata.name,
                                 description=pvdata.description,
                                 type=pvdata.type,
                                 data_table=pvdata.data_table,
                                 deadtime=pvdata.deadtime,
                                 deadband=pvdata.deadband,
                                 graph_lo=pvdata.graph_lo,
                                 graph_hi=pvdata.graph_hi,
                                 graph_type=pvdata.graph_type,
                                 active=pvdata.active)
                nextdb.execute(q)

        # update run info
        # add this new run to the runs table
        tnow = time.time()
        notes = f"{tformat(tnow)} to {tformat(MAX_EPOCH)}"
        self.db = DatabaseConnection(self.config.cache_db, self.config)
        self.db.insert('runs', db=dbname, notes=notes,
                       start_time=tnow, stop_time=MAX_EPOCH)

        self.tables  = self.db.tables
        itab = self.db.tables['info']
        self.db.execute(itab.update().where(
            itab.c.process=='archive').values(db=dbname))
        return dbname

    def get_info(self, process='cache'):
        " get value from info table"
        return self.db.get_rows('info', where={'process': process},
                                limit_one=True, none_if_empty=True)

    def get_pidstatus(self, process='cache'):
        row = self.get_info(process=process)
        return row.pid, row.status

    def set_info(self, process='cache', **kws):
        " set value(s) in the info table"
        # print("Set info ", process, kws)
        self.db.update('info', where={'process': process}, **kws)

    def get_pvnames(self):
        """ generate self.pvnames: a list of pvnames in the cache"""
        pvnames = []
        for row in self.db.get_rows('cache'):
            pvnames.append(row.pvname)
            self.pvtypes[row.pvname] = row.type
            if row.pvname not in self.pvs and self.pvconnect:
                self.pvs[row.pvname] = get_pv(row.pvname)
        return pvnames

    def get_enum_strings(self):
        """
        return dict of PVs and enum_strings for enum PVs
        """
        out = {}
        for row in self.db.get_rows('pvextra', where={'notes': 'enum_strs'}):
            out[row.pv] = json.loads(row.data)
        return out

    def update_pvextra(self):
        """
        update extra PV data such as (and currently only) enum strings
        """
        if not self.pvconnect:
            return
        # update enum strings for enum PVs
        all_enumstrs = {}
        for row in self.db.get_rows('pvextra', where={'notes': 'enum_strs'}):
            all_enumstrs[row.pv] = row.data

        for row in self.db.get_rows('cache'):
            pvname = row.pvname
            if row.type == 'enum' and pvname in self.pvs:
                if not self.pvs[pvname].connected:
                    continue
                enumstrs = self.pvs[pvname].enum_strs
                if enumstrs is not None and len(enumstrs) > 0:
                    enumstrs = json.dumps(list(enumstrs))
                    if pvname not in all_enumstrs:
                        self.db.insert('pvextra', pv=pvname,
                                       notes='enum_strs',
                                       data=enumstrs)
                    elif enumstrs != all_enumstrs[pvname]:
                        self.db.update('pvextra',
                                       where={'pv':pvname, 'notes': 'enum_strs'},
                                       data=enumstrs)

    def get_narchived(self, time_ago=60):
        """
        return the number of values archived by the archive in the past N seconds.
        if limit is set, return as  soon as this limit is seen to be exceeded
        this is useful when checking if any values have been cached.
        """
        n = 0
        archdbname = self.get_info(process='archive').db
        archdb = DatabaseConnection(archdbname, self.config)

        start_time = Decimal(time.time() - time_ago)
        for i in range(1, 129):
            tab = archdb.tables[f'pvdat{i:03}']
            q = tab.select().where(tab.c.time > start_time)
            n += len(archdb.execute(q).fetchall())
        return n

    def show_status(self, with_archive=True, cache_time=60, archive_time=60):
        info = row2dict(self.get_info(process='cache'))
        try:
            proc = psutil.Process(info['pid'])
            tnow = datetime.fromtimestamp(round(time.time()))
            tstart = datetime.fromtimestamp(round(proc.create_time()))
            runtime = str(tnow-tstart)
        except:
            runtime = 'unknown'
        stat_tab = [["Process", "Status", "Database", "PID", "Runtime",
                     "New Values", "Action", "Time(sec)", "Last TimeStamp"]]
        stat_tab.append(["Cache", info['status'], self.db.dbname, info['pid'],
                         runtime, len(self.get_values(time_ago=cache_time)),
                         'PVs updated', cache_time, info['datetime']])

        if with_archive:
            info = row2dict(self.get_info(process='archive'))
            try:
                proc = psutil.Process(info['pid'])
                tnow = datetime.fromtimestamp(round(time.time()))
                tstart = datetime.fromtimestamp(round(proc.create_time()))
                runtime = str(tnow-tstart)
            except:
                runtime = 'unknown'
            stat_tab.append(["Archive", info['status'], info['db'], info['pid'],
                             runtime, self.get_narchived(time_ago=archive_time),
                             'Values archived', archive_time, info['datetime']])
        print(tabulate(stat_tab, headers='firstrow', tablefmt='simple_grid'))

    def set_runinfo(self, dbname=None):
        """set timerange for an archive run"""
        tmin = MAX_EPOCH
        tmax = 0
        current_dbname = self.get_info(process='archive').db
        if dbname is None:
            dbname = current_dbname
        if dbname == current_dbname:
            tmax = MAX_EPOCH - 1.0
        archdb = DatabaseConnection(dbname, self.config)
        for i in range(1, 129):
            tabname = f'pvdat{i:03}'
            oldest = archdb.get_rows(tabname, order_by='time',
                                     order_desc=False, limit_one=True)
            newest = archdb.get_rows(tabname, order_by='time',
                                     order_desc=True, limit_one=True)
            print("  info: ", dbname, i, tformat(oldest[0]), tformat(newest[0]))
            try:
                tmin = min(tmin, float(oldest.time))
                tmax = max(tmax, float(newest.time))
            except ValueError:
                print( "failed to get times ")

        tmin = max(1, min(tmin, MAX_EPOCH-1))
        tmax = max(1, min(tmax, MAX_EPOCH-1))

        if dbname == current_dbname:
            notes = f"{tformat(tmin)} to <currently running>"
        else:
            notes = f"{tformat(tmin)} to {tformat(tmax)}"

        logging.info(f"set run info for {dbname}: {notes}")

        self.db.update('runs', where={'db': dbname},
                       notes=notes, start_time=tmin, stop_time=tmax)

    def connect_pvs(self):
        """connect to unconnected PVs, make sure callback is defined"""
        nnew = 0
        if not self.pvconnect:
            return 0
        t0 = time.time()
        for pvname, pv in self.pvs.items():
            if pv.connected:
                if len(pv.callbacks) < 1:
                    nnew += 1
                    cval = pv.get(as_string=True)
                    pv.add_callback(self.onChanges)
                    self.data[pvname] = (pv.value, cval, time.time())
                    if pvname in self.alert_data:
                        self.alert_data[pvname]['last_value'] = pv.value
                        self.alert_data[pvname]['last_notice'] = time.time() - 30.0
        # self.update_pvextra()
        self.log(f"connect to pvs: {time.time()-t0:.3f} sec, {nnew} new entries")
        return nnew

    def onChanges(self, pvname=None, value=None, char_value=None, timestamp=None, **kws):
        if value is not None and pvname is not None:
            if timestamp is None:
                timestamp = time.time()
            self.data[pvname] = (value, char_value, timestamp)
            if pvname in self.alert_data:
                self.alert_data[pvname]['last_value'] = value

    def mainloop(self):
        "main loop"
        if not self.pvconnect:
            raise ValueError('cannot run mainloop with pvconnect=False')

        self.pid = os.getpid()
        self.log(f'Starting Epics PV Caching: pid = {self.pid}')
        t0 = time.time()
        self.set_info(process='cache', status='running', pid=self.pid, ts=t0,
                      datetime=tformat(t0))

        with open(self.pidfile, 'w') as fout:
            fout.write(f'{self.pid}\n')

        nconn = self.connect_pvs()
        self.update_pvextra()

        msg = f'{nconn}/{len(self.pvs)} pvs connected, ready to run.'
        self.log(f'{msg} Cache Process ID= {self.pid}')

        for alert in self.alert_data.values():
            if alert['last_value'] is None and alert['pvname'] in self.pvs:
                pv = self.pvs[alert['pvname']]
                if pv.connected:
                    alert['last_value'] = pv.value

        for name, alert in self.alert_data.items():
            self.log(f"Add Alert: {name} / {alert['pvname']}", level='debug')

        status_str = '%d values cached since last notice %d loops (%.1f sec)'
        ncached, nloop, last_report, last_info, last_request_process = 0, 0, 0, 0, 0
        collecting = True
        while collecting:
            try:
                time.sleep(0.002)
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
                    last_report = last_request_process = time.time() + 1
            # process alerts every 15 seconds:
            if time.time() > last_request_process + float(self.config.cache_alert_period):
                self.process_requests()
                self.process_alerts()
                last_request_process = time.time()
            # report and connect unconnected PVs once ever 5 minutes
            if tnow > last_report + float(self.config.cache_report_period):
                self.log(status_str % (ncached, nloop, float(self.config.cache_report_period)))
                last_report = tnow
                self.read_alert_table()
                self.connect_pvs()
                ncached = 0
                nloop = 0
            if tnow > last_report + float(self.config.cache_update_pvextra):
                self.update_pvextra()

            if len(self.pvtypes) < len(self.pvs):
                for row in self.db.get_rows('cache'):
                    if row.pvname not in self.pvtypes:
                        self.pvtypes[row.pvname] = row.type
                #self.get_pvnames()
                print("$ got pvs ", len(self.pvs), len(self.pvtypes))
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
            self.log(f'adding PV: {pvname}', level='debug')
            time.sleep(0.1)
            return self.get_full(pvname, add=False)
        return self.db.get_rows('cache', where={'pvname': pvname},
                                none_if_empty=True, limit_one=True)

    def get(self, pvname, add=False, use_char=True):
        " return cached value of pv"
        ret = self.get_full(pvname, add=add)
        if ret is None:
            return None
        field = 'cvalue' if use_char else 'value'
        return getattr(ret, field)

    def update_cache(self):
        # take new pvnames as of right now, and pop off the latest
        # values for these pvs.
        # Note: be careful to not set self.data = {}, which would
        # blow away any changes that occur during this processing
        #
        # IMPORTANT NOTE: the data size might change during processing!
        newpvs = list(self.data.keys())
        if len(newpvs) == 0:
            return 0
        newdata = {}
        for pvname in newpvs:
            val, cval, tstamp = self.data.pop(pvname)
            if isinstance(val, np.ndarray):
                val = val.tolist()
            if self.pvtypes.get(pvname, '') == 'double':
                cval = hformat(val)
            newdata[pvname] = {'ts': Decimal(tstamp),
                               'value': clean_bytes(val),
                               'cvalue': clean_bytes(cval)}

        ctab = self.tables['cache']
        # print("##### UPDATE CACHE ", len(newdata), time.ctime())
        update_where = ctab.update().where
        with Session(self.db.engine) as session, session.begin():
            ex = session.execute
            for pvname, dat in newdata.items():
                ex(update_where(ctab.c.pvname==pvname).values(**dat))
            session.flush()
        return len(newdata)

    def get_values(self, all=False, time_ago=60.0, time_order=False):
        """get recent values from cache
        """
        tab = self.tables['cache']
        query = tab.select()
        if not all:
            query = query.where(tab.c.ts>Decimal(time.time() - time_ago))
        if time_order:
            query = query.order_by(tab.c.ts)
        return self.db.execute(query).fetchall()

    def get_values_dict(self, all=False, time_ago=60.0):
        """return a dict with ids as keys and (pvname, value, cvalue, ts) as value
        useful for web app, and easy to update previously retrieved dict:
            vdict = self.get_values_dict(all=True)
            while True:
                 vdict.update(self.get_values_dict(time_ago=10)
                 time.sleep(1)
        """
        out = {}
        for row in self.get_values(all=all, time_ago=time_ago, time_order=False):
            out[row.pvname] = {'id': row.id, 'value': row.value,
                               'cvalue': row.cvalue, 'dtype': row.type,
                               'ts': float(row.ts)}
        return out

    def add_pv(self, pvlist, with_motor_fields=True):
        """ add a PV or list of PVs to the cache"""
        if isinstance(pvlist, str):
            pvlist = [pvlist]

        pvlist = [normalize_pvname(pvname) for pvname in pvlist]
        current_pvnames = self.get_pvnames()
        for pvname in pvlist:
            if pvname not in self.pvs:
                self.pvs[pvname] = get_pv(pvname)

        pvs_to_add = []
        for pvname in pvlist:
            thispv = self.pvs[pvname]
            if not thispv.connected:
                for i in range(20):
                    if not thispv.connected:
                        time.sleep(0.1)
            if (thispv.connected and pvname not in current_pvnames and
                pvname not in pvs_to_add):
                pvs_to_add.append(thispv)
        time.sleep(0.01)
        def make_insertfields(pv):
            dtype = pv.type
            dtype = dtype.replace('ctrl_', '').replace('time_', '')
            dtype = dtype.replace('short', 'int').replace('long', 'int')
            dtype = dtype.replace('float', 'double')
            out = {'pvname': pv.pvname,
                    'value': pv.value,
                    'cvalue': pv.char_value,
                    'active': 'yes',
                    'type': dtype,
                    'ts': Decimal(time.time())}
            # if dtype == 'enum':
            #     out['enum_strs'] = pv.enum_strs
            return out

        idicts = []
        all_pairs = [[p.pvname for p in pvs_to_add]]
        for pv in pvs_to_add:
            out = make_insertfields(pv)
            idicts.append(out)
            prefix = out['pvname']
            if prefix.endswith('.VAL'):
                dname = prefix.replace('.VAL', '.DESC')
                dpv = get_pv(dname)
                dpv.wait_for_connection(timeout=1)
                if dpv.connected:
                    self.pvs[dname] = dpv
                    idicts.append(make_insertfields(dpv))
                    all_pairs.append([prefix, dname])

            # check if PV is for a motor, add motor fields
            if (with_motor_fields and
                prefix.endswith('.VAL') and
                out['type'] == 'double'):
                prefix = prefix[:-4]
                rtype = get_pv(f"{prefix}.RTYP")
                time.sleep(0.010)
                if 'motor' == rtype.get():
                    m_names = [f"{prefix}{i}" for i in motor_fields]
                    m_names.extend([f"{prefix}.DESC"])
                    m_pvs = [get_pv(n) for n in m_names]
                    for epv in m_pvs:
                        epv.wait_for_connection(timeout=1)
                    for epv in m_pvs:
                        if epv.connected and epv.pvname not in self.pvs:
                            self.pvs[epv.pvname] = epv
                            idicts.append(make_insertfields(epv))
                    all_pairs.append(m_names)
        print("PVs to ADD : ", len(idicts))
        self.db.insert_many('cache', idicts)
        for pairs in all_pairs:
            self.set_all_pairs(pairs, score=10)
        self.db.flush()
        self.connect_pvs()
        self.update_pvextra()


    def add_pvfile(self, fname):
        """read a file that lists pvnames and add them  to the PV cache
        PVs listed on the same line will be considered 'pairs'
        """
        with  open(fname, 'r') as fh:
            lines = fh.readlines()
        self.logger.info(f'Adding PVs listed in file: {fname}')

        for line in lines:
            line = line[:-1].strip()
            if '#' in line:
                line = line[:line.find('#')].strip()
            if len(line)<2:
                continue

            pvnames = line.replace(',',' ').split()
            self.add_pv(pvnames)
            if len(pvnames) > 1:
                self.set_all_pairs(pvnames)


    def drop_pv(self, pvname):
        """ request that a PV (by name) be dropped from the cache"""
        self.db.insert('requests', pvname=pvname, action='drop', ts=time.time())

        if pvname in self.pvs:
            thispv = self.pvs.pop(pvname)
            thispv.clear_callbacks()
        if pvname in self.data:
            self.data.pop(pvname)

    def process_alerts(self):
        "handling alerts"
        for pvname, alert in self.alert_data.items():
            value = alert.get('last_value', None)
            if (alert['active'] == 'no' or value is None or
                time.time() < (alert['last_notice'] + alert['timeout'])):
                continue

            # coerce values to strings or floats for comparisons
            convert = str
            if isinstance(value,(int, float)):
                convert = float

            value     = convert(value)
            trippoint = convert(alert['trippoint'])
            cmp       = OPS[alert['compare']]
            was_ok    = 'ok' == alert['status']

            # compute new alarm status: note form  'value.__ne__(trippoint)'
            now_ok = not getattr(value, cmp)(trippoint)
            status = 'ok' if now_ok else 'alarm'
            self.db.update('alerts', where={'pvname': pvname}, status=status)
            alert['status'] = status
            notify = was_ok and not now_ok

            msg = [f"check alert: {pvname}", f"status={status}", f"val={value}",
                   f"trip={trippoint}", f"notify={notify}"]
            self.log(', '.join(msg))
            if notify:
                alert['last_notice'] = time.time()
                self.send_alert_mail(alert, value)
                self.log(f"Alert sent for PV={pvname}, Label={alert['name']}")
            # the value has been checked, so we can set 'last_value' to
            # None so that the alert will not be checked until the value changes.
            alert['last_value'] = None


    def send_alert_mail(self, alert, value):
        """ send an alert email from an alert dict holding
        the appropriate row of the alert table.
        """
        mail_to = alert['mailto']
        pvname = alert['pvname']
        label  = alert['name']
        compare= alert['compare']
        msg    = alert['mailmsg']

        if mail_to in ('', None) or pvname in ('', None):
            return

        mail_to = mail_to.replace('\r','').replace('\n','')

        trippoint = alert['trippoint']
        if isinstance(trippoint, bytes):
            trippoint = trippoint.decode('utf-8')
        subject   = f"[Epics Alert] {label}"

        if msg in ('', None):
            msg = "error message"

        msg  = clean_mail_message(msg)

        opstr = 'not equal to'
        for tok,desc in zip(OPTOKENS, OPSTRINGS):
            if tok == compare:
                opstr = desc

        # fill in 'template' values in mail message
        for k, v in list({'PV': pvname,  'LABEL':label,
                          'COMP': opstr, 'VALUE': str(value),
                          'TRIP': trippoint}.items()):
            msg = msg.replace(f"%{k}%", v)

        pvrow = self.get_full(pvname, add=False)

        mlines = [f"Subject: {subject}", ""]
        mlines.extend(msg.split('\n'))

        # replace %PV(XX)%
        re_showpv = re.compile(r".*%PV\((.*)\)%.*").match
        for i, line in enumerate(mlines):
            nmatch = 0
            match = re_showpv(line)
            while match is not None and nmatch<25:
                pvn = match.groups()[0]
                line = line.replace(f'%PV({pvn})%', self.get(pvn))
                match = re_showpv(line)
                nmatch = nmatch + 1
            mlines[i] = line
        conf = self.config

        url = f"{conf.web_baseurl}{conf.web_url}/plot/1days/now"
        mlines.append(f"See {url}/{pvrow.pvname}")
        message = '\n'.join(mlines)
        try:
            s = SMTP(conf.mail_server)
            s.sendmail(conf.mail_from, mail_to, message)
            s.quit()
            self.log(f"send alert mail for '{pvname}' to: {mail_to}")
        except:
            self.log(f"Could not send alert mail for '{pvname}'.",
                     level='warn')

    def process_requests(self):
        " process requests for new PV's to be cached"
        req = self.db.get_rows('requests')
        if len(req) == 0:
            return

        self.log(f"processing {len(req)} requests")
        for row in req:
            pvname, action = row.pvname, row.action
            msg = 'could not process request for'
            if valid_pvname(pvname):
                if 'suspend' == action:
                    if pvname in self.pvs:
                        self.pvs[pvname].clear_callbacks()
                        self.db.update('cache', where={'pvname': pvname}, active='no')
                        self.db.delete_rows('requests', where={'id': row.id})
                        msg = 'suspended'
                elif 'drop' == action:
                    self.db.delete_rows('cache', where={'pvname': pvname})
                    self.db.delete_rows('requests', where={'id': row.id})
                    if pvname in self.pvs:
                        self.pvs[pvname].clear_callbacks()
                        self.pvs.pop(pvname)
                    msg = 'dropped'
                elif 'add' == action:
                    self.add_pv(pvname)
                    if pvname not in self.pvs:
                        pv = get_pv(pvname)
                        conn = pv.wait_for_connection(timeout=3.0)
                        if conn:
                            self.pvs[pv.pvname] = pv
                            cval = pv.get(as_string=True)
                            val = pv.value
                            if isinstance(val, np.ndarray):
                                val = val.tolist()
                            self.db.insert('cache.', pvname=pvname, type=pv.type,
                                           ts=time.time(),
                                           value=clean_bytes(val),
                                           cvalue=clean_bytes(cval),
                                           active='yes')
                            self.db.delete_rows('requests', where={'id': row.id})
                            msg = 'added'
                        else:
                            msg = 'could not add'
                    else:
                        msg = 'already added'
            self.log(f'{msg} PV: {pvname}')
        time.sleep(0.01)

    def read_alert_table(self):
        self.alert_data = {}
        for alert in self.db.get_rows('alerts'):
            pvname = alert.pvname
            if pvname not in self.alert_data:
                self.alert_data[pvname] = row2dict(alert)
            else:
                self.alert_data[pvname].update(row2dict(alert))
            if 'last_notice' not in self.alert_data[pvname]:
                self.alert_data[pvname]['last_notice'] = 0
            if self.alert_data[pvname].get('last_value', None) is None:
                value = None
                if pvname in self.pvs:
                    value = self.pvs[pvname].value
                self.alert_data[pvname]['last_value'] = value

        return self.alert_data

    def get_alerts(self):
        return self.read_alert_table()

    def get_runs(self, start_time=0, stop_time=None):
        runs = self.db.get_rows('runs')
        if stop_time is None:
            stop_time = MAX_EPOCH
        out = []
        for run in runs:
            if run.stop_time  > start_time and run.start_time < stop_time:
                out.append(run)
        return out

    def get_related(self, pvname, limit=None):
        """get related PVs for the supplied pvname, a dictionary ordered by score"""

        out = {}
        if limit is None:
            limit = 1.e99
        a = self.db.get_rows('pairs', where={'pv1': pvname}, order_by='score')
        b = self.db.get_rows('pairs', where={'pv2': pvname}, order_by='score')
        for row in a + b:
            other = row.pv1 if row.pv2 == pvname else row.pv2
            out[other] = row.score
        # sort by score descending
        out = dict(sorted(out.items(), key=lambda i: -i[1]))

        # maybe limit to top scores
        if limit is not None and limit < len(out):
            out = dict(list(out.items())[:limit])
        return out

    def get_pair_score(self, pvname1, pvname2):
        "get pair score for 2 pvnames"
        score = 0
        nrows = 0
        if pvname1 == pvname2:
            return 0
        pvname1, pvname2 = sorted([pvname1, pvname2])
        for where in ({'pv1': pvname1, 'pv2': pvname2},
                      {'pv1': pvname2, 'pv2': pvname1}):
            rows = self.db.get_rows('pairs', where=where)
            if len(rows) > 0:
                for row in rows:
                    score += row.score
                    nrows += 1
        if nrows > 1:
            self.db.delete_rows('pairs', where={'pv1': pvname2, 'pv2': pvname1})
            self.db.update('pairs', where={'pv1': pvname1, 'pv2': pvname2},
                           score=score)
        return score

    def set_pair_score(self, pvname1, pvname2, score=None, increment=1):
        "set pair score for 2 pvnames"
        if pvname1 == pvname2:
            self.log(f"Cannot set pair score for PV with itself '{pvname1}'",
                     level='warn')
        if pvname1 not in self.pvs or pvname2 not in self.pvs:
            self.log(f"Cannot set pair score for unknown PVS '{pvname1}' and '{pvname2}",
                     level='warn')

        pvname1, pvname2 = sorted([pvname1, pvname2])
        current_score = self.get_pair_score(pvname1, pvname2)
        if score is None:
            score = increment + current_score

        if current_score > 0:
            self.db.update('pairs', where={'pv1': pvname1, 'pv2': pvname2},
                           score=score)
        else:
            self.db.insert('pairs', pv1=pvname1, pv2=pvname2, score=score)

    def increment_pair_score(self, pv1, pv2, increment=1):
        """increase by the pair score for two pvs """
        self.set_pair_score(pv1, pv2, score=None, increment=increment)

    def set_all_pairs(self, pvlist, score=10):
        """for a list/tuple of pvs, set all pair scores
        to be at least the provided score"""
        _pvlist = [normalize_pvname(p) for p in pvlist]
        scores = []
        for i, pvname1 in enumerate(_pvlist):
            for pvname2 in _pvlist[i+1:]:
                p1, p2 = sorted([pvname1, pvname2])
                if p1 == p2:
                    continue
                current_score = self.get_pair_score(p1, p2)
                if current_score > 1:
                    self.db.delete_rows('pairs', where={'pv1': p1, 'pv2': p2})
                score = max(current_score, score)
                scores.append({'pv1': p1, 'pv2': p2, 'score': score})

        self.db.insert_many('pairs', scores)
