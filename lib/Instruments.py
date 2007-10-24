import time
import smtplib

from MasterDB import MasterDB
from util import normalize_pvname
from config import mailserver, mailfrom, cgi_url

class Instruments(MasterDB):
    """ interface to Instruments"""
    def __init__(self,**kw):
        MasterDB.__init__(self)
        self.inst_pos  = self.db.tables['instrument_positions']

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

    def save_instrument_position(self,inst_id=None,name=None,ts=None,inst=None,station=None):
        if inst_id is None:
            inst_id = self.get_instrument_id(name=inst,station=station)

            if len(inst_id) == 0: warn = 'no'
            if len(inst_id)  > 1: warn = 'multiple'
            if len(inst_id) != 1:
                print "warning: %s instruments found for name='%s', station='%s'" %(warn,inst,station)
                if len(inst_id)==0:
                    return
            inst_id = inst_id[0]

        if inst_id < 0: return
        if ts is None: ts = time.time()
        if name is None: name = time.ctime()
        self.inst_pos.insert(inst=inst_id,name=name,ts=ts)

    def hide_position(self,inst_id=None,name=None,hide=True):
        """ hide or unhide namesd positions for an instrument id"""
        if inst_id is None or name is None: return
        active = 'yes'
        if hide: active = 'no'
        where = "inst=%i and name='%s'" % (inst_id,name)
        self.inst_pos.update(active=active,where=where)

    def get_positions(self,inst_id=None,inst=None,station=None,name=None,get_hidden=False):
        """return a list of (id,name,ts) for instrument_positions
        (that is the position id, position name, timestamp for position)
        given an instrument name, and optionally a station name, and
        optionally a position name """

        out = []
        where = '1=1'
        if not get_hidden:
            where = "active='yes'"
        if inst_id is None:
            inst_id = self.get_instrument_id(name=inst,station=station)

            if len(inst_id) > 0:
                if name is not None: where = "name='%s'" %  name
                for inst in inst_id:
                    ret = self.inst_pos.select(where="%s and inst=%i" % (where,inst))
                    for r in ret:
                        out.append((r['id'],r['name'],r['ts'],r['active']))
        else:
            inst_id = int(inst_id)
            if name is not None: where = "name='%s'" %  name
            ret = self.inst_pos.select(where="%s and inst=%i" % (where,inst_id))
            for r in ret:
                out.append((r['id'],r['name'],r['ts'],r['active']))
        return out

    def get_instrument_values(self,inst_id=None,position=None,ts=None):
        """ given an instrument id and either a position name or timestamp
        return a list of (pvname,values) tuples for all PVs in that instrument.
        returns list_of_pv_values
        where list_of_pv_values is a list of (pvname,values)

        Note that the values returned may be None, meaning 'unknown'
        """
        if position is not None:
            try:
                pos_id,pos_name,ts,a = self.get_positions(inst_id=inst_id,name=position)[0]
            except IndexError:
                ts = None

        if ts is None:
            return ([], 0)

        pvs = [i['pvname'] for i in self.inst_pvs.select(where="inst=%i" % inst_id)]

        data = dict.fromkeys(pvs,None)

        from Archiver import Archiver
        a = Archiver()

        for pvname in pvs:
            for d in a.get_data(pvname,t0=ts,t1=ts)[0]:
                if d[0] <= ts:
                    data[pvname] = d[1]

        a.db.close()
        
        pvnames = data.keys()
        pvnames.sort()
        vals = [(p,data[p]) for p in pvnames]
        return vals,ts


class Alerts(MasterDB):
    """ interface to alerts"""

    comps = {'==':'eq', 'eq':'eq', '!=':'ne', 'ne':'ne',
             '<=':'le', 'le':'le', '<' :'lt', 'lt':'lt',
             '>=':'ge', 'ge':'ge', '>' :'gt', 'gt':'gt'}
    
    ops = {'eq':'__eq__', 'ne':'__ne__', 
           'le':'__le__', 'lt':'__lt__', 
           'ge':'__ge__', 'gt':'__gt__'}

    opnames = {'eq':'equal', 'ne':'not equal', 
               'le':'less than or equal to', 'lt':'less than', 
               'ge':'greater than or equal to', 'gt':'greater than'}

    statusmap = {False:'alarm',True:'ok'}
    
    mail_fmt = "From: %s\r\nSubject: %s\r\n%s\n"
    default_mail="""
An alarm condition was detected for PV='%PV%'
The current value = %VALUE%.
This is %COMP% the trip point value of %TRIP%
"""

    
    def __init__(self,**kw):
        MasterDB.__init__(self)
        self.alerts = self.db.tables['alerts']

    def show_all(self):
        for i in self.alerts.select():
            print i

    def show_for_pv(self,pvname):
        pvname = normalize_pvname(pvname)
        for i in self.alerts.select(where="pvname='%s'" % pvname):
            print i

    def add(self,pvname=None,name=None,
            mailto=None,  mailmsg=None,
            compare='ne', trippoint=None, **kw):

        if pvname is None:
            print 'must provide a pvname for an alert'
            return
        
        pvname = normalize_pvname(pvname)        

        if name is None: name = pvname
           
        if pvname not in self.pvnames: self.add_pv(pvname)

        active = 'yes'
        if mailto  is None:
            mailto  =''
            active  = 'no'
        if mailmsg is None:
            mailmsg =''
            active  = 'no'            
        if trippoint is None:
            trippoint = 0.
            active = 'no'
        if compare in self.comps.keys(): compare = self.comps[compare]
        
        self.alerts.update(name=name,pvname=pvname,active=active,
                           mailto=mailto,mailmsg=mailmsg,
                           compare=compare, trippoint=trippoint)
        
    def __make_where(self,id=None, name=None,pvname=None):
        where = '1=1'
        if id is not None:
            where = "%s and id=%i" % (where,int(id))

        if name is not None:
            where = "%s and name='%s'" % (where,clean_input(name))

        if pvname is not None:
            where = "%s and pvname='%s'" % (where, normalize_pvname(pvname))
        return where
    
        
    def get_id(self,name=None,pvname=None,get_one=True):
        """ return id for alert given a name or pvname:
        if more than one match is found, either the first
        or all matches will be returned, depending on the
        value of 'get_one'
        """
        where = self.__make_where(name=name, pvname=pvname)
        ret = self.alerts.select(where=where)
        if get_one: ret = ret[0]
        return ret
        
    def suspend(self,id=None,name=None,pvname=None):
        "disable alert"
        where = self.__make_where(id=id, name=name, pvname=pvname)
        self.alerts.update(active='no',where=where)

    def activate(self,id=None,name=None,pvname=None):
        "enable alert"
        where = self.__make_where(id=id, name=name, pvname=pvname)
        self.alerts.update(active='yes',where=where)
    
    def check(self,id,value,sendmail=False):
        "returns alert state: True for OK, False for Alarm"
        print 'check alarm id ',id , ' for value ', value
        where = "id=%i"% id
        alarm = self.alerts.select_one(where=where)
        
        # if alarm is not active, return True / 'value is ok'
        if 'no' == alarm['active']: return True

        # coerce values to strings or floats for comparisons
        if isinstance(value,(int,long,complex)):
            value      = float(value)
        elif not isinstance(value,str):
            value   = str(value)
            
        if isinstance(value,float):
            trippoint  = float(alarm['trippoint'])
        else:
            trippoint  = str(alarm['trippoint'])

        old_value_ok = alarm['status'] == 'ok'
        
        compare = alarm['compare']
        if not self.ops.has_key(compare):  compare = 'ne'
        
        value_ok = not getattr(value,self.ops[compare])(trippoint)

        # no change in status?? return.
        if old_value_ok == value_ok:
            print 'NO CHANGE:::: would return value_ok = ', value_ok
        
        status = self.statusmap[value_ok]

        self.alerts.update(status=status,where=where)
        print 'Alarm status = ', status

        mailto = alarm['mailto']
        pvname = alarm['pvname']
        if sendmail and not value_ok and mailto is not None:
            print 'sending mail'

            mailto  = tuple(mailto.split(','))
            subject = "[Epics Alarm] %s " % pvname
            content = alarm['mailmsg']
            if content is None:  content = self.default_mail

            # here, we template-ize the stored content!
            params = {'PV': pvname, 'VALUE': str(value),
                      'COMP': self.opnames.get(compare),
                      'TRIP': str(trippoint)}
            for k,v in params.items():
                compare = compare.replace("%%%s%%" % k, v)
                    
            compare = "%s\nSee %s/status.py?pv=%s" % (compare,cgi_url,pvname)

            print 'Mail content==='
            msg       = self.mail_fmt  % (mailfrom, subject, content)

            print mailfrom
            print mailto
            print msg

            # s  = smtplib.SMTP(mailserver)
            # s.sendmail(mailfrom,mailto,msg)
            # s.quit()
            
        return value_ok


        
        
