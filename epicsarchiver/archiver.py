#!/usr/bin/python
import time
import sys
import os
import logging

from decimal import Decimal

from sqlalchemy import MetaData, create_engine, engine, text

import epics

from .util import (normalize_pvname, get_force_update_time, tformat,
                   clean_bytes, clean_string, SEC_DAY,
                   DatabaseConnection, None_or_one,
                   MAX_EPOCH, valid_pvname, motor_fields,
                   get_config)

from .cache import Cache

class Archiver:
    MIN_TIME = 100
    sql_insert  = "insert into %s (pv_id,time,value) values (%i,%f,%s)"
    def __init__(self, envvar='PVARCH_CONFIG', **kws):
        self.config = get_config(envar=envvar, **kws)
        self.cache = Cache(envvar=envvar, pvconnect=False, **kws)
        self.log  = self.cache.log
        self.dbname = None
        self.force_checktime = 0
        self.last_collect = 0
        self.dtime_limbo = {}
        self.use_archivedb()

    def use_archivedb(self, dbname=None):
        if dbname is None:
            dbname = self.cache.get_info(process='archive').db
        self.dbname = dbname
        self.db = DatabaseConnection(self.dbname, self.config)
        self.pvtable = self.db.tables['pv']
        # self.pvs    = {k: v for k,v in self.cache.pvs.items()}
        self.pvinfo = {}
        self.refresh_pvinfo()

    def refresh_pvinfo(self):
        """
        refresh the 'self.pvinfo' dictionary by re-reading the
        database settings for pvs in the pv table
        may also add pvs to the .pvs dict
        """
        for pvdata in self.pvtable.select().execute().fetchall():
            name = pvdata.name
            if name in self.pvinfo:
                self.pvinfo[name].update(pvdata.items())
            else:
                dat = dict(pvdata.items())
                dat.update({'last_ts': 0,'last_value':None,
                            'force_time': get_force_update_time()})
                self.pvinfo[name] = dat
                # if name not in self.pvs:
                #    self.pvs[name] = epics.get_pv(name)


    def get_pvinfo(self, pvname):
        """return pvinfo data (a dict) for a pv, and also ensures that it
        is in the pvinfo dictionary
        """
        if pvname not in self.pvinfo:
            query = self.pvtable.select(whereclause=text('name=%s'% pvname))
            dat = None_or_one(query.execute().fetchall())
            if dat is None:
                self.add_pv(pvname)
                time.sleep(0.01)
                dat = None_or_one(query.execute().fetchall())
                if dat is None:
                    return None
            dat.update({'last_ts': 0,'last_value':None,
                        'force_time': get_force_update_time()})
            self.pvinfo[pvname] = dat
        return self.pvinfo[pvname]

    def dbs_for_time(self, t0=None, t1=None):
        """ return list of databases with data in the given time range"""
        if t0 is None:
            t0 = time.time() - SEC_DAY
        if t1 is None:
            t1 = time.time() + SEC_DAY
        return [run.db for run in self.cache.get_runs(start_time=t0, stop_time=t1)]

    def get_value_at_time(self, pvname, t):
        """
        return (time, value) for an archived value of a pv at one time
        time will be a float timestamp, and value will be a string.

        returns None, None if not found or error
        """
        pvname = normalize_pvname(pvname)
        if pvname not in self.pvinfo:
            self.log("pv %s not found" % (pvname), level='warn')

        dbname = self.dbs_for_time(t, t+1)[0]
        db = DatabaseConnection(dbname, self.config)
        wclause = text("name='%s'" % pvname)
        row = db.tables['pv'].select(whereclause=wclause).execute().fetchall()
        if len(row) < 1:
            self.log("no data table for  %" % (pvname), level='warn')

        row = row[0]
        dtable = db.tables[row.data_table]
        query  = dtable.select().where(dtable.c.pv_id==row.id)
        query  = query.where(dtable.c.time>=Decimal(t-SEC_DAY))
        query  = query.where(dtable.c.time<=Decimal(t+0.5))
        query  = query.order_by(dtable.c.time.desc()).limit(100)
        rows = query.execute().fetchall()
        out = None, None
        for row in rows:
            rtime = float(row.time)
            if rtime < t:
                out = rtime, row.value
                break
        if isinstance(out[1], bytes):
            out = (out[0], out[1].decode('utf-8'))
        return out

    def get_data(self, pvname, tmin=None, tmax=None, with_current=None):
        """
        get data for a PV over a time range, optionally including the current value
        """
        pvname = normalize_pvname(pvname)
        if pvname not in self.pvinfo:
            self.log("pv %s not found" % (pvname), level='warn')

        if tmin is None:
            tmin = time.time() - SEC_DAY
        if tmax is None:
            tmax = time.time()
        data = []
        for dbname in self.dbs_for_time(tmin-SEC_DAY, tmax+5):
            db = DatabaseConnection(dbname, self.config)
            wclause = text("name='%s'" % pvname)
            row = db.tables['pv'].select(whereclause=wclause).execute().fetchall()
            if len(row) < 1:
                self.log("no data table for  %" % (pvname), level='warn')

            row = row[0]
            dtable = db.tables[row.data_table]
            query  = dtable.select().where(dtable.c.pv_id==row.id)
            query  = query.where(dtable.c.time>=Decimal(tmin-SEC_DAY))
            query  = query.where(dtable.c.time<=Decimal(tmax+0.5))
            rows   = query.order_by(dtable.c.time).execute().fetchall()

            if len(data) == 0:  # include 1 datapoint before tmin
                for row in reversed(rows):
                    rtime = float(row.time)
                    if rtime <= tmin:
                        val = row.value
                        if isinstance(val, bytes):
                            val = val.decode('utf-8')
                        data = [(rtime, val)]
                        break

            for row in rows:
                rtime = float(row.time)
                if rtime >= tmin and rtime <= tmax:
                    val = row.value
                    if isinstance(val, bytes):
                        val = val.decode('utf-8')
                    data.append((float(row.time), val))
        if with_current:
            cur = self.cache.get_full(pvname)
            val = cur.value
            if isinstance(val, bytes):
                val = val.decode('utf-8')
            data.append((float(cur.ts),  val))
        return data


    def add_pv(self, name, description=None, graph={}, deadtime=None, deadband=None):
        """add PV to the archive database: expected to take a while"""
        pvname = normalize_pvname(name)

        if not valid_pvname(pvname):
            self.log("## Archiver add_pv invalid pvname = '%s'" % pvname,
                     level='warn')
            return

        if pvname in self.pvinfo:
            if 'yes' == self.pvinfo[pvname]['active']:
                self.log("PV %s is already in database." % pvname)
            else:
                self.log("PV %s is in database, reactivating." % pvname)
                self.pvinfo[pvname]['active'] = 'yes'
            return

        # create an Epics PV, check that it's valid
        try:
            pv = epics.get_pv(pvname)
            pv.get(timeout=5)
            pv.get_ctrlvars()
            typ = pv.type
            count = pv.count
            prec  = pv.precision
            connected = pv.connected
        except:
            connected = False

        if not pv.connected:
            self.log("cannot connect to PV '%s'" % pvname, level='warn')
            return

        # determine type
        dtype = 'string'
        pvtype = pv.type.replace('ctrl_', '').replace('time_', '')
        if pvtype in ('int', 'long', 'short'):
            dtype = 'int'
        elif pvtype in ('enum',):
            dtype = 'enum'
        elif pvtype in ('double', 'float'):
            dtype = 'double'

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
                    dp = epics.get_pv(descpv)
                    description = dp.get(as_string=True)
                except:
                    pass
        if description is None:
            description = ''

        # set graph default settings
        gr = {'high':'', 'low':'', 'type':'normal'}
        gr.update(graph)
        if dtype == 'enum':
            x = pv.get(as_string=True)
            gr['type'] = 'discrete'
            gr['low'] = 0
            gr['high'] =  len(pv.enum_strs)
        elif dtype == 'double':
            gr['type'] = 'normal'
            dx = description.lower()
            for i in ('cathode','pirani','pressure'):
                if dx.find(i) >= 0:
                    gr['type'] = 'log'

        if deadtime is None:
            deadtime = float(self.config.pv_deadtime_double)
            if dtype in ('enum', 'string'):
                deadtime = float(self.config.pv_deadtime_enum)
            if gr['type'] == 'log':
                deadtime = 5.0  # (pressures change very frequently)

        if deadband is None:
            deadband = 1.e-5
            if gr['type'] == 'log':
                deadband = 1.e-4
            if prec is not None:
                deadband = 10**(-(prec+1))
            if dtype in ('enum','string'):
                deadband =  0.5

        self.log('Archiver adding PV: %s, table: %s' % (pvname,table))

        pvtab = self.pvtable
        pvtab.insert().execute(name=pvname,
                               type=dtype,
                               description=description,
                               data_table=table,
                               deadtime=deadtime,
                               deadband=deadband,
                               graph_lo=gr['low'],
                               graph_hi=gr['high'],
                               graph_type=gr['type'])

        time.sleep(0.01)
        pvdata = pvtab.select().where(pvtab.c.name==pvname).execute().fetchone()

        dat = dict(pvdata.items())
        dat.update({'last_ts': 0,'last_value':None,
                    'force_time': get_force_update_time()})
        self.pvinfo[name] = dat
        self.update_value(pvname, time.time(), pv.value)


    def update_value(self, name, ts, val):
        "insert value into appropriate table "
        if val is None:
            return
        if ts is None or ts < self.MIN_TIME:
            ts = time.time()

        self.pvinfo[name]['last_ts'] =  float(ts)
        self.pvinfo[name]['last_value'] =  val

        info = self.pvinfo[name]
        dval = clean_bytes(val, maxlen=4096)
        self.db.tables[info['data_table']].insert().execute(pv_id=info['id'],
                                                            time=ts,
                                                            value=dval)

    def collect(self):
        """ one pass of collecting new values, deciding what to archive"""
        newvals, forced = {},{}
        tnow = time.time()
        dt  =  3.0*(tnow - self.last_collect)
        self.last_collect = tnow
        for dat in self.cache.get_values(time_ago=dt):
            name  = dat.pvname
            if name not in self.pvinfo:
                self.add_pv(name)
            if dat.active == 'no':
                continue
            val = dat.value
            ts  = float(dat.ts)

            info = self.pvinfo[name]
            do_save = ts > float(info['last_ts'])+float(info['deadtime'])
            if do_save:
                if 'double' in dat.type or 'float' in dat.type:
                    last_val  = self.pvinfo[name]['last_value']
                    try:
                        v, o = float(val), float(last_val)
                        do_save = abs(v-o) > abs(info['deadband'])
                    except:
                        pass
            if do_save:
                newvals[name] = (ts, val)
                if name in self.dtime_limbo:
                    self.dtime_limbo.pop(name)
            elif ts > (0.001 + float(info['last_ts'])):
                # pv changed, but inside 'deadtime': put it in limbo!
                self.dtime_limbo[name] = (ts, val)

        # now look through the "limbo list" and insert the most recent change
        # iff the last insert was longer ago than the deadtime:
        tnow = time.time()
        # print('====== Collect: ',  len(newvals), len(self.dtime_limbo), time.ctime())
        for name in list(self.dtime_limbo.keys()):
            info = self.pvinfo[name]
            if info['active'] == 'yes':
                last_ts  = float(info['last_ts'])
                deadtime = float(info['deadtime'])
                if tnow > (last_ts + deadtime):
                    newvals[name] = self.dtime_limbo.pop(name)

        n_new     = len(newvals)
        n_forced  = 0
        # check for stale values and re-read db settings every 5 minutes
        if tnow > (self.force_checktime + 300):
            # print('looking for stale values %s'  %time.ctime() )
            self.force_checktime = tnow
            self.refresh_pvinfo()
            for p in self.cache.get_pvnames():
                if p not in self.pvinfo:
                    self.add_pv(p)
            fullcache = {}
            for row in self.cache.tables['cache'].select().execute().fetchall():
                fullcache[row.pvname] = row.ts, row.value

            for name, info in self.pvinfo.items():
                if info['active'] == 'no':
                    continue
                try:
                    force = tnow > float(info['last_ts'])+float(info['force_time'])
                except:
                    force = False
                if force and name in fullcache and name not in newvals:
                    newvals[name] = time.time(), fullcache[name][1]
                    n_forced = n_forced + 1

        for name, data in newvals.items():
            self.update_value(name, data[0], data[1])
        return len(newvals), n_forced


    def get_nchanged(self, minutes=10, limit=None):
        """
        return the number of values archived in the past minutes.
        if limit is set, return as  soon as this limit is seen to be exceeded
        this is useful when checking if any values have been cached.
        """
        n = 0
        whereclause = text("time>%d" % (time.time()-minutes*60.0))
        for i in range(1, 129):
            q = self.db.tables['pvdat%3.3d' % i].select(whereclause=whereclause)
            n += len(q.execute().fetchall())
        return n

    def mainloop(self,verbose=False):
        t0 = time.time()
        self.log('connecting to archive database')
        self.use_archivedb()
        self.last_collect = t0
        self.pid = os.getpid()
        self.cache.set_info(process='archive', pid=self.pid, status='running')

        collecting = True
        n_changed = n_forced = n_loop = last_report = 0
        last_info = 0
        msg = "%d new values, %d forced entries since last notice. %d loops"
        self.log('start archiving to %s ' % self.dbname)
        while collecting:
            try:
                epics.poll(evt=0.003, iot=1.0)
                n1, n2 = self.collect()
                n_changed = n_changed + n1
                n_forced  = n_forced  + n2
                n_loop = n_loop + 1

                tnow = time.time()
                if tnow > last_report + float(self.config.archive_report_period):
                    self.log(msg % (n_changed, n_forced, n_loop))
                    n_changed = n_forced = n_loop = 0
                    last_report = tnow
                if tnow > last_info + 2.0:
                    self.cache.set_info(process='archive', ts=tnow,
                                        datetime=tformat(tnow))
                    last_info = tnow

            except KeyboardInterrupt:
                self.log('Interrupted by user.', level='warn')
                collecting = False
                break

            pid, status = self.cache.get_pidstatus(process='archive')
            if status in ('stopping', 'offline') or pid != self.pid:
                logging.debug('no longer main archiving program, exiting.')
                collecting = False

        self.cache.set_info(process='archive', status='offline')
        return None

    def shutdown(self):
        self.cache.set_info(process='archive', status='stopping')
