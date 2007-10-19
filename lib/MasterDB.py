import time
import EpicsCA
from SimpleDB import SimpleDB, SimpleTable
from config import dbuser, dbpass, dbhost, master_db
from util import normalize_pvname, tformat, \
     MAX_EPOCH, SEC_DAY, motor_fields

class MasterDB:
    """ general interface to Master Database of Epics Archiver.
    This is used by both Cache and ArchiveMaster classes, which
    point to the same Master database but generally have different
    functionality
    """
    runs_title= '|  database         |         date range              | duration (days)|'
    runs_line = '|-------------------|---------------------------------|----------------|'

    def __init__(self,db=None, **kw):
        if db is None:
            self.db = SimpleDB(user=dbuser, passwd=dbpass,
                               host=dbhost, dbname=master_db)
        else:
            self.db = db
            
        self.info    = self.db.tables['info']
        self.cache   = self.db.tables['cache']
        self.runs    = self.db.tables['runs']
        self.pairs   = self.db.tables['pairs']
        self.arch_db = self._get_info('db',  process='archive')
        self.get_pvnames()
        
    def use_master(self):
        self.db.use(master_db)

    def use_current_archive(self):
        self.arch_db = self._get_info('db',  process='archive')        
        self.db.use(self.arch_db)

        
    def get_pvnames(self):
        """ generate self.pvnames: a list of pvnames in the cache"""
        self.pvnames = []
        for i in self.cache.select():
            if i['pvname'] not in self.pvnames:
                self.pvnames.append(i['pvname'])


    def request_pv_cache(self,pvname):
        """request a PV to be included in caching.
        will take effect once a 'process_requests' is executed."""
        npv = normalize_pvname(pvname)
        if npv in self.pvnames: return

        cmd = "insert into requests (pvname,action) values ('%s','add')" % npv
        self.db.execute(cmd)

    def add_epics_pv(self,pv):
        """ add an epics PV to the cache"""
        if not pv.connected:  return

        self.get_pvnames()
        if pv.pvname in self.pvnames: return

        EpicsCA.pend_io(0.1)

        self.cache.insert(pvname=pv.pvname,type=pv.type)

        where = "pvname='%s'" % pv.pvname
        o = self.cache.select_one(where=where)
        if o['pvname'] not in self.pvnames:
            self.pvnames.append(o['pvname'])



    def drop_pv(self,pvname):
        """drop a PV from the caching process -- really this 'suspends updates'
        will take effect once a 'process_requests' is executed."""
        npv = normalize_pvname(pvname)

        if not npv in self.pvnames: return

        cmd = "insert into requests (pvname,action) values ('%s','suspend')" % npv
        self.sql_exec(cmd)

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
                    self.request_pv_cache(pvname)
            self.set_allpairs(fields)
            EpicsCA.pend_event(0.01)
        else:
            if EpicsCA.PV(pvname,connect=True) is not None:
                self.request_pv_cache(pvname)
        EpicsCA.pend_event(0.01)
        EpicsCA.pend_io(1.0)


    def get_recent(self,dt=60):
        where = "ts>%f order by ts" % (time.time() - dt)
        return self.cache.select(where=where)
        
    def dbs_for_time(self, t0=SEC_DAY, t1=MAX_EPOCH):
        """ return list of databases with data in the given time range"""
        timerange = ( min(t0,t1) - SEC_DAY, max(t0,t1) + SEC_DAY)
        where = "stop_time>=%i and start_time<=%i order by start_time"
        r = []
        for i in self.runs.select(where=where % timerange):
            if i['db'] not in r: r.append(i['db'])
        return r

    def close(self): self.db.close()
    
    def _get_info(self,name='db',process='archive'):
        try:
            return self.info.select_one(where="process='%s'" % process)[name]
        except:
            return None

    def _set_info(self,process='archive',**kw):
        self.info.update("process='%s'" % process, **kw)

    def get_cache_status(self):
        return self._get_info('status', process='cache')

    def get_arch_status(self):
        return self._get_info('status', process='archive')

    def get_cache_pid(self):
        return self._get_info('pid',    process='cache')

    def get_arch_pid(self):
        return self._get_info('pid',    process='archive')

    def set_cache_pid(self,pid):
        return self._set_info(pid=pid,  process='cache')

    def set_arch_pid(self,pid):
        return self._set_info(pid=pid,  process='archive')

    def set_cache_status(self,status):
        return self._set_info(status=status,  process='cache')

    def set_arch_status(self,status):
        return self._set_info(status=status,  process='archive')

    def arch_report(self,minutes=10):
        self.db.use(self.arch_db)
        n = 0
        dt = (time.time()-minutes*60.)
        q = "select * from pvdat%3.3i where time > %f " 
        for i in range(1,129):
            r = self.db.exec_fetch(q % (i,dt))
            n = n + len(r)

        self.db.use(master_db)
        o = ["Current Database=%s, status=%s, PID=%i" %(self.arch_db,
                                                        self.get_arch_status(),
                                                        self.get_arch_pid()),
             "%i values archived in past %i minutes" % (n, minutes)]
        return o

    def cache_report(self,brief=False,dt=60):
        out = []
        pid = self.get_cache_pid()
        ret = self.cache.select(where="ts> %i order by ts" % (time.time()-dt))
        fmt = "  %s %.25s = %s"
        if not brief:
            for r in ret:
                out.append(fmt % (tformat(t=r['ts'],format="%H:%M:%S"),
                                  r['pvname']+' '*20, r['value']) )
                    
        fmt = '%i PVs had values updated in the past %i seconds. pid=%i'
        out.append(fmt % (len(ret),dt,pid))
        return out
        
    def runs_report(self):
        r = []
        for i in self.runs.select(where='1=1 order by start_time desc limit 10'):
            timefmt = "%6.2f "
            if  i['db'] == self.arch_db:
                timefmt = "%6.2f*"
                i['stop_time'] = time.time()
            i['days'] = timefmt % ((i['stop_time'] - i['start_time'])/(24*3600.0))
            r.append("| %(db)16s  | %(notes)30s  |   %(days)10s   |" % i)
        r.reverse()
        out = [self.runs_title,self.runs_line]
        for i in r: out.append(i)
        out.append(self.runs_line)
        return out

    ##
    ## Pairs
    def get_related_pvs(self,pv,minscore=1):
        """return a list of related pvs to the provided pv
        with a minumum pair score"""
        
        out = []
        tmp = []
        npv = normalize_pvname(pv)
        if npv not in self.pvnames: return out
        for i in ('pv1','pv2'):
            where = "%s='%s' and score>=%i order by score" 
            for j in self.pairs.select(where = where % (i,npv,minscore)):
                tmp.append((j['score'],j['pv1'],j['pv2']))
        tmp.sort()
        for r in tmp:
            if   r[1] == npv:  out.append(r[2])
            elif r[2] == npv:  out.append(r[1])
        out.reverse()
        return out

    def __get_pvpairs(self,pv1,pv2):
        p = [normalize_pvname(pv1),normalize_pvname(pv2)]
        p.sort()
        return tuple(p)
    
        
    def get_pair_score(self,pv1,pv2):
        p = self.__get_pvpairs(pv1,pv2)
        if not ((p[0] in self.pvnames) and (p[1] in self.pvnames)):
            return 0
        where = "pv1='%s' and pv2='%s'" % p
        score = -1
        o  = self.pairs.select_one(where=where)
        if o.has_key('score'): score = int(o['score'])
        return score

    def set_pair_score(self,pv1,pv2,score=None):
        p = self.__get_pvpairs(pv1,pv2)
        for i in p:
            if i not in self.pvnames:
                self.request_pv_cache(i)
        
        current_score  = self.get_pair_score(p[0],p[1])
        if score is None: score = 1 + current_score
       
        if current_score <= 0:
            q = "insert into pairs set score=%i, pv1='%s', pv2='%s'"
        else:
            q = "update pairs set score=%i where pv1='%s' and pv2='%s'"
        # print q % (score,p[0],p[1])        
        self.db.exec_fetch(q % (score,p[0],p[1]))
        
    def increment_pair_score(self,pv1,pv2):
        """increase by 1 the pair score for two pvs """
        self.set_pair_score(pv1,pv2,score=None)

    def set_allpairs(self,pvlist,score=10):
        """for a list/tuple of pvs, set all pair scores
        to be at least the provided score"""
        # print 'This is set_allpairs ', pvlist, type(pvlist)
        if not isinstance(pvlist,(tuple,list)): return
        _tmp = list(pvlist[:])
        while _tmp:
            a = _tmp.pop()
            for b in _tmp:
                if self.get_pair_score(a,b)<score:
                    self.set_pair_score(a,b,score=score)
                    
        self.pairs.select()

    def get_all_scores(self,pv1,pv2,score):
        self.pairs.select()

        
class InstrumentDB(MasterDB):
    """ interface to Instruments"""

    def __init__(self,**kw):
        MasterDB.__init__(self)

        self.stations  = self.db.tables['stations']
        self.stations  = self.db.tables['stations']         
        self.instruments = self.db.tables['instruments']         
        self.inst_pvs  = self.db.tables['instrument_pvs']
        self.inst_pos  = self.db.tables['instrument_positions']

    ##
    ## Instruments
    def get_instruments_with_pv(self,pv):
        """ return a list of (instrument ids, inst name, station name) for
        instruments which  contain a named pv"""
        inames = []
        pvn = normalize_pvname(pv)
        for r in self.inst_pvs.select(where="pvname='%s'" % pvn):
            inst = self.instruments.select_one(where="id=%i" % r['inst'])
            sta  = self.stations.select_one(where="id=%i" % inst['station'])
            inames.append((r['inst'],inst['name'],sta['name']))
        return inames

    def create_station(self,name=None,notes=''):
        " create a station by name"
        if name is not None:
            self.stations.insert(name=name,notes=notes)

    def list_stations(self):
        " return a list of dictionaries for current stations"
        return  self.stations.select()

    def list_instruments(self,station=None):
        """ return a list of dictionaries for all defined instruments
        providing an optional station name will return all defined
        instruments in that station
        """                
        where = '1=1'
        if station is not None:
            s_id = self.get_station_id(name=station)
            if s_id is not None:  where="station=%i" % s_id

        return  self.instruments.select(where=where)

    def get_station_id(self,name=None):
        "return station id from station name"
        ret = None
        if name is not None:
            o = self.stations.select_one(where="name='%s'" % name)
            ret = o['id']
        return ret

    def get_instrument_names_from_id(self,id=0):
        for j in self.list_instruments():
            if id == j['id']:
                name = j['name']
                o = self.stations.select_one(where="id=%i" % j['station'])
                station = o['name']
                return name,station
        return (None,None)

    def get_instrument_id(self,name=None,station=None):
        """return list of instrument ids from name -- note
        that there may be more than one instrument with the
        same name!!  Use optional station argument to
        limit instrument choices"""

        ilist = self.list_instruments(station=station)
        if name is None: [i['id'] for i in ilist]            
        out = []
        for i in ilist:
            if i['name'] == name: out.append(i['id'])
        return out

    def create_instrument(self,name=None,station=None,notes=''):
        station_id = self.get_station_id(station)
        if station_id is None or name is None: return
        self.instruments.insert(name=name,station=station_id,notes=notes)

    def get_instruments(self,name=None,station=None):
        where = '1=1'
        if name is not None:
            where = "name='%s'" % name
        if station is not None:
            sta = self.get_station_id(station)
            if sta is not None:
                where = "%s and station=%i" % (where,sta)

        return self.instruments.select(where=where)

    def remove_instrument_pvs(self,pvlist,name=None,station=None,notes=''):
        insts = self.get_instruments(name=name,station=station)
        if len(insts)> 1:
            print 'multiple instruments matched name/station=%s/%s' % (name,station)
            return None
        if not isinstance(pvlist,(tuple,list)):
            print 'must provide list of PVs for instrument %s' % (name)
            return None
        inst_id = insts[0]['id']
        q = "delete from instrument_pvs where inst=%i and pvname='%s'"
        for pvname in pvlist:
            pvn = normalize_pvname(pvname)
            self.inst_pvs.db.execute(q % (inst_id, pvn))
        

    def set_instrument_pvs(self,pvlist,name=None,station=None,notes=''):
        insts = self.get_instruments(name=name,station=station)
        if len(insts)> 1:
            print 'multiple instruments matched name/station=%s/%s' % (name,station)
            return None
        if not isinstance(pvlist,(tuple,list)):
            print 'must provide list of PVs for instrument %s' % (name)
            return None
        inst_id = insts[0]['id']
        self.get_pvnames()
        for pvname in pvlist:
            pvn = normalize_pvname(pvname)

            where = "inst=%i and pvname='%s'" % (inst_id,pvn)
            x = self.inst_pvs.select_one(where=where)
            if x == {}:
                x = self.inst_pvs.insert(pvname=pvn,inst=inst_id)
            if pvn not in self.pvnames:  self.add_pv(pvn)

        # set pair scores
        allpvs = self.get_instrument_pvs(name=name,station=station)
        if len(allpvs) > 1:
            self.set_allpairs(allpvs)


    def get_instrument_pvs(self,name=None,station=None,**kw):
        insts = self.get_instruments(name=name,station=station)
        out = []
        if len(insts)> 1:
            print 'multiple instruments matched name/station=%s/%s' % (name,station)
        else:
            where = "inst=%i" % insts[0]['id']
            x = self.inst_pvs.select(where=where)
            for i in x: out.append(i['pvname'])
        
        return out

    def save_instrument_position(self,name=None,ts=None,inst=None,station=None):
        inst_id = self.get_instrument_id(name=inst,station=station)
        if len(inst_id) == 0: warn = 'no'
        if len(inst_id)  > 1: warn = 'multiple'
        if len(inst_id) != 1:
            print "warning: %s instruments found for name='%s', station='%s'" %(warn,inst,station)
            if len(inst_id)==0:
                return

        inst_id = inst_id[0]
        if ts is None: ts = time.time()
        if name is None: name = time.ctime()
        self.inst_pos.insert(inst=inst_id,name=name,ts=ts)

    def get_positions(self,inst_id=None,inst=None,station=None,name=None):
        """return a list of (id,name,ts) for instrument_positions
        (that is the position id, position name, timestamp for position)
        given an instrument name, and optionally a station name, and
        optionally a position name """
        
        out = []
        where = '1=1'

        if inst_id is None:
            inst_id = self.get_instrument_id(name=inst,station=station)

            if len(inst_id) > 0:
                if name is not None: where = "name='%s'" %  name
                for inst in inst_id:
                    ret = self.inst_pos.select(where="%s and inst=%i" % (where,inst))
                    for r in ret:
                        out.append((r['id'],r['name'],r['ts']))
        elif isinstance(inst_id,int):
            if name is not None: where = "name='%s'" %  name
            ret = self.inst_pos.select(where="%s and inst=%i" % (where,inst_id))
            for r in ret:
                out.append((r['id'],r['name'],r['ts']))
            
        return out

    def get_instrument_values(self,inst_id=None,position=None,ts=None):
        """ given an instrument id and either a position name or timestamp
        return a tuple of (pvname,values) for all PVs in that instrument. """

        print 'GET INST VALS ' ,inst_id, type(inst_id), position,ts

        if position is not None:
            p = self.get_positions(inst_id=inst_id,name=position)
            print ' get_position returned: ', p
            # print 'POS:  ', ts

        out = []
        if ts is None:
            print 'cannot find timestamp to look up settings'
            return out


        x =  self.inst_pvs.select(where="inst=%i" % inst_id)
        print x
        
        pvs = [i['pvname'] for i in self.inst_pvs.select(where="inst=%i" % inst_id)]
        print 'PVS: '
        print pvs
        
        from Archiver import Archiver
        a = Archiver()

        data = {}
        for arch_db in self.dbs_for_time(t0=ts,t1=ts):
            self.db.use(self.arch_db)
            for pvname in pvs:
                for d in a.get_data(pvname,t0=ts,t1=ts)[0]:
                    if d[0] <= ts:
                        data[pvname] = d[1]

        self.use_master()
        a.db.close()


        pvnames = data.keys() ; pvnames.sort()
        for p in pvnames: out.append((p,data[p]))
            
        return out,ts

    
# 
#             
#         
#     def get_position_values(self,position):
#         """ given a position tuple (returned from list_positions)
#         return a dictionary of (pvname,values) for all PVs in that position.
#         """
#         pos_id,name,ts = position
#         
#         x = self.inst_pos.select_one(where="id=%i" % (pos_id))
#         pvs = [i['pvname'] for i in self.inst_pvs.select(where="inst=%i" % x['inst'])]
#         
#         from Archiver import Archiver
#         a = Archiver()
# 
#         data = {}
#         for arch_db in self.dbs_for_time(t0=ts,t1=ts):
#             self.db.use(self.arch_db)
#             for pvname in pvs:
#                 for d in a.get_data(pvname,t0=ts,t1=ts)[0]:
#                     if d[0] <= ts:
#                         data[pvname] = d[1]
# 
#             
#         self.use_master()
#         out = []
#         pvnames = data.keys() ; pvnames.sort()
#         for p in pvnames: out.append((p,data[p]))
#             
#         return out
