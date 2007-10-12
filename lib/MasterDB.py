import time
from SimpleDB import SimpleDB, SimpleTable
from config import dbuser, dbpass, dbhost, master_db

class MasterDB:
    """ general interface to Master Database of Epics Archiver.
    This is used by both Cache and ArchiveMaster classes, which
    point to the same Master database but generally have different
    functionality
    """
    runs_title= '|  database         |         date range              | duration (days)|'
    runs_line = '|-------------------|---------------------------------|----------------|'

    def __init__(self,**kw):
        self.db = SimpleDB(user=dbuser, passwd=dbpass,
                           host=dbhost, dbname=master_db)
        self._table_pvnames = self.db.tables['pvnames']
        self.info    = self.db.tables['info']
        self.cache   = self.db.tables['cache']
        self.runs    = self.db.tables['runs']
        self.pairs   = self.db.tables['pairs'] 

        self.arch_db = self._get_info('db',  process='archive')

        self.get_pvnames()
        
    def get_pvnames(self):
        """ generate pvnames: a dict of pvnames and their ids: {id:pvname}
        and pvids: a dict of {pvname:id} pairs"""
        self.pvids = {}
        self.xxpvidsxx   = {}
        for i in self._table_pvnames.select():
            self.pvids[i['pvname']] = i['id']
            self.xxpvidsxx[i['id']]       = i['pvname']

    def close(self): self.db.close()
    
    def _get_info(self,name='db',process='archive'):
        try:
            return self.info.select_one(where="process='%s'" % process)[name]
        except:
            return None

    def _set_info(self,process='archive',**kws):
        print '_set info ', kws
        self.info.update(set=kws, where="process='%s'" % process)

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
                                  r['name']+' '*20, r['value']) )
                    
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
        npv = normalize_pvname(pv)
        if not self.pvids.has_key(npv): return out
        ipv = self.pvids[npv]
        tmp = []
        for i in ('pv1','pv2'):
            where = "%s=%i and score>=%i order by score" 
            for j in self.pairs.select(where = where % (i,ipv,minscore)):
                tmp.append((j['score'],j['pv1'],j['pv2']))
        tmp.sort()
        for r in tmp:
            j = 1
            if r[1] == ipv: j = 2
            n = self.xxpvidsxx[r[j]]
            if n not in out: out.append(n)
        out.reverse()
        return out

    def get_pair_score(self,pv1,pv2):
        p = [pv1.strip(),pv2.strip()]
        p.sort()
        if not (self.pvids.has_key(p[0]) and self.pvids.has_key(p[1])):
            return 0
        where = "pv1=%i and pv2=%i" % (self.pvids[p[0]],self.pvids[p[1]])
        return int(self.pairs.select_one(where=where)['score']) 

    def set_pair_score(self,pv1,pv2,score=None):
        p = [pv1.strip(),pv2.strip()]
        p.sort()
        if not (self.pvids.has_key(p[0]) and self.pvids.has_key(p[1])):
            return
        
        current_score  = self.get_pair_score(p[0],p[1])
        if score is None: score = 1 + current_score
       
        ids = (self.pvids[p[0]],self.pvids[p[1]])

        if current_score == 0:
            self.pairs.update(score=score, where="pv1=%i and pv2=%i" %ids)
        else:
            self.pairs.insert(pv1=ids[0],pv2=ids[1],score=score)

    def increment_pair_score(self,pv1,pv2):
        """increase by 1 the pair score for two pvs """
        self.set_pair_score(pv1,pv2,score=None)

    def set_allpairs(self,pvlist,score=10):
        """for a list/tuple of pvs, set all pair scores
        to be at least the provided score"""
        if not isinstance(pvlist,(tuple,list)): return
        _tmp = list(pvlist[:])
        while _tmp:
            a = _tmp.pop()
            for bin in _tmp:
                if self.get_pair_score(a,b)<score:
                    self.set_pair_score(a,b,score=score)
                    
            
        self.pairs.select()

    def get_all_scores(self,pv1,pv2,score):
        self.pairs.select()
