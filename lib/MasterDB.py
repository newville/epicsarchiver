import time
import EpicsCA
from SimpleDB import SimpleDB, SimpleTable
from config import dbuser, dbpass, dbhost, master_db, cgi_url
from util import normalize_pvname, tformat, \
     MAX_EPOCH, SEC_DAY, motor_fields

class MasterDB:
    """ general interface to Master Database of Epics Archiver.
    This is used by both by itself, and is sublcassed by
    Cache, ArchiveMaster, Instruments, and Alerts.

    Because of the multiple uses and especially because it is used
    as the sole interface by some Web processes, the API here may
    seem a bit disjointed, with a partial interface for Pairs and
    Alerts, but this allows many processes to have exactly one
    database connection.    
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
        self.stations  = self.db.tables['stations']
        self.instruments = self.db.tables['instruments']
        self.inst_pvs  = self.db.tables['instrument_pvs']
        self.alerts = self.db.tables['alerts']
        
        self.arch_db = self._get_info('db',  process='archive')

        self.get_pvnames()
        
    def use_master(self):
        "point db cursor to use master database"
        self.db.use(master_db)

    def use_current_archive(self):
        "point db cursor to use current archive database"
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


    def drop_pv(self,pvname):
        """drop a PV from the caching process -- really this 'suspends updates'
        will take effect once a 'process_requests' is executed."""
        npv = normalize_pvname(pvname)
        if not npv in self.pvnames: return

        cmd = "insert into requests (pvname,action) values ('%s','suspend')" % npv
        self.sql_exec(cmd)

    def get_recent(self,dt=60):
        """get recent additions to the cache, those
        inserted in the last  dt  seconds."""
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

    def close(self):
        "close db connection"
        self.db.close()
    
    def _get_info(self,name='db',process='archive'):
        " get value from info table"
        try:
            return self.info.select_one(where="process='%s'" % process)[name]
        except:
            return None

    def _set_info(self,process='archive',**kw):
        " set value(s) in the info table"        
        self.info.update("process='%s'" % process, **kw)

    def get_cache_status(self):
        " get status of caching process"
        return self._get_info('status', process='cache')

    def get_arch_status(self):
        " get status of archiving process"
        return self._get_info('status', process='archive')

    def set_cache_status(self,status):
        " set status of caching process"                
        return self._set_info(status=status,  process='cache')

    def set_arch_status(self,status):
        " set status of archiving process"        
        return self._set_info(status=status,  process='archive')

    def get_cache_pid(self):
        " get pid of caching process"
        return self._get_info('pid',    process='cache')

    def get_arch_pid(self):
        " get pid of archiving process"        
        return self._get_info('pid',    process='archive')

    def set_cache_pid(self,pid):
        " set pid of caching process"
        return self._set_info(pid=pid,  process='cache')

    def set_arch_pid(self,pid):
        " set pid of archiving process"        
        return self._set_info(pid=pid,  process='archive')

    ##
    ## Status/Activity Reports 
    def arch_report(self,minutes=10):
        """return a report (list of text lines) for archiving process,
        giving the number of values archived in the past minutes.
        """
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
        """return a report (list of text lines) for caching process,
        giving number of values cached in the past dt seconds.
        Use 'brief=False' to show which PVs have been cached.
        """
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
        """return a report (list of text lines) for the archiving runs
        showing the time ranges for the (at most) 10 most recent runs.
        """
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
        "fix and sort 2 pvs for use in the pairs tables"
        p = [normalize_pvname(pv1),normalize_pvname(pv2)]
        p.sort()
        return tuple(p)
    
        
    def get_pair_score(self,pv1,pv2):
        "set pair score for 2 pvs"        
        p = self.__get_pvpairs(pv1,pv2)
        if not ((p[0] in self.pvnames) and (p[1] in self.pvnames)):
            return 0
        where = "pv1='%s' and pv2='%s'" % p
        score = -1
        o  = self.pairs.select_one(where=where)
        if o.has_key('score'): score = int(o['score'])
        return score

    def set_pair_score(self,pv1,pv2,score=None):
        "set pair score for 2 pvs"
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

    ##
    ## Alerts
    def check_alert(self,id,value,sendmail=False):
        """returns alert state: True for Value is OK,
        False for Alarm
        may send email alert if necessary
        """
        where = "id=%i"% id
        alarm = self.alerts.select_one(where=where)
        
        # if alarm is not active, return True / 'value is ok'
        if 'no' == alarm['active']: return True

        old_value_ok = alarm['status'] == 'ok'

        # coerce values to strings or floats for comparisons
        convert = str
        if isinstance(value,(int,long,float,complex)):
            convert = float
        value     = convert(value)
        trippoint = convert(alarm['trippoint'])

        cmp = self.ops[alarm['compare']]
        
        # compute new alarm status, of the form
        #                value.__ne__(trippoint)
        value_ok = not getattr(value,cmp)(trippoint)

        if old_value_ok != value_ok:
            # update the status filed in the alerts table
            status = 'alarm'
            if value_ok: status = 'ok'
            self.alerts.update(status=status,where=where)
           
            # send mail if value is now not ok!
            if sendmail and not value_ok:
                self.sendmail(alarm,value)

        return value_ok

            
    def sendmail(self,alarm,value):
        """ send an alert email from an alarm dict holding
        the appropriate row of the alert table.        
        """
        mailto = alarm['mailto']
        pvname = alarm['pvname']
        if mailto in ('', None) or pvname in ('', None): return

        compare   = alarm['compare']
        trippoint = str(alarm['trippoint'])
        mailto    = tuple(mailto.split(','))
        subject   = "[Epics Alarm] %s " % pvname

        msg       = alarm['mailmsg']
        if msg is None: msg = """Hello,
  An alarm was detected for PV = '%PV%'
  The current value = %VALUE%. This is
  %COMP% the trip point value of %TRIP%
  """
        opnames = {'eq':'equal', 'ne':'not equal', 
                   'le':'less than or equal to', 'lt':'less than', 
                   'ge':'greater than or equal to', 'gt':'greater than'}
        
        for k,v in {'PV': pvname, 'VALUE': str(value),
                    'COMP': opnames[compare],
                    'TRIP': str(trippoint)}.items():
            msg = msg.replace("%%%s%%" % k, v)
            
        msg = "From: %s\r\nSubject: %s\r\n%s\nSee %s/status.py?pv=%s\n" % \
              (mailfrom,subject,msg,cgi_url,pvname)

        s  = smtplib.SMTP(mailserver)
        print  mailfrom,mailto,msg
        # s.sendmail(mailfrom,mailto,msg)
        s.quit()
