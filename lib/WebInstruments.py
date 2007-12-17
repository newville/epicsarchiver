#!/usr/bin/env python

import time
from EpicsArchiver import Instruments, config

from HTMLWriter import HTMLWriter, jscal_get_date

from util import normalize_pvname,  clean_input, \
     tformat, time_str2sec, write_saverestore

pagetitle  = config.pagetitle

footer     = config.footer
mainpage   = "%s/show.py"  % config.cgi_url
instpage   = "%s/show.py/instrument"  % config.cgi_url
pvinfopage = "%s/admin.py/pvinfo" % config.cgi_url

DEBUG = False

class WebInstruments(HTMLWriter):
    POS_DATE = '__(position_by_date)__'
    html_title = 'Epics Instruments'
    
    def __init__(self,dbconn=None,**kw):

        HTMLWriter.__init__(self)
        self.arch   = Instruments(dbconn=dbconn)
        self.dbconn  = self.arch.dbconn
        self.kw  = {'station_sel':'', 'newstation':'',
                    'station':'', 'instrument':'','pv':'',
                    'station_add':'','inst_id':-1,
                    'submit': '' }


    def show(self,**kw):
        self.kw.update(kw)

        pv = self.kw['pv']
        station = self.kw['station']
        instrument = self.kw['instrument']

        wr = self.write                
        
        self.starthtml()
        self.show_links(pv=pv,help='instruments',active_tab='Instruments')
        if DEBUG: self.show_dict(self.kw)
        
        inst_id = -1        
        if self.kw.has_key('inst_id'):
            try:
                inst_id = int(self.kw['inst_id'])
            except:
                pass

        newpos_name = ''
        if self.kw.has_key('newpos_name'):
            newpos_name =clean_input(self.kw.get('newpos_name','').strip())

        tsec = -1
        if self.kw.has_key('date'):
            try:
                tsec  = time_str2sec(self.kw.get('date','').strip())
            except:
                pass
                

        try:
            use_newstation = int(self.kw.get('newstation','0').strip())==1
            
        except:
            use_newstation = False
            
        if not use_newstation and inst_id>0:
            # we may act on new position name or lookup-by-date
            if newpos_name!='':
                # save new position name
                self.arch.save_instrument_position(inst_id = inst_id, name=newpos_name)
                instrument,station = self.arch.get_instrument_names_from_id(inst_id)
            elif tsec>0:
                # look up position by date
                return self.view_position(position= self.POS_DATE,
                                          inst= inst_id, date=tsec)

        self.kw['station_sel'] = ''
        
        # wr(" <h3> Instruments  </h3> ")
        
        self.show_station_choices()

        self.startform(action=instpage,hiddenkeys=('pv',))
        if station == '':
            wr("Please select a station.")
        else:
            # a large outer 2 column table: 
            ## self.starttable
            wr("""<table cellpadding=2 border=0 rules='cols'><tr valign='top'><td width=30%% align='top'>
            <table bgcolor='#F9F9F5' border=0 frame='box'><tr><td>Instruments for %s:</td></tr>
            <tr><td><a href='%s/add_instrument?station=%s'>
            &lt;add an instrument&gt; </a></td></tr>""" % (station,mainpage,station))
            
            self.instruments = {}
            for s in self.arch.list_instruments(station=station):
                self.instruments[s['name']] = (s['id'],s['notes'])

            inst_list = self.instruments.keys() ; inst_list.sort()
            
            for inst in inst_list:
                ilink = "<a href='%s?station=%s&instrument=%s'>%s</a>" % (instpage,station,inst,inst)
                wr("<tr><td>%s</td></tr>" % ilink)

            wr("</table></td><td><table align='center' valign='top' frame='border'>")   # right side : positions for this instrument
            if instrument == '':
                wr("<tr><td colspan=2>Please select an instrument</td></tr>")
            else:
                inst_id = self.instruments[instrument][0]
                
                positions = self.arch.get_positions(inst=instrument,station=station,
                                                    get_hidden=False)
                pvlist    = self.arch.get_instrument_pvs(name=instrument,station=station)
                pvlist.sort()

                wr("<input type='hidden' name='instrument_name'  value='%s'>" % instrument)
                wr("<input type='hidden' name='inst_id'  value=%i>" % inst_id)
                wr("<tr><td align='center' colspan=2>%s: %s</td></tr>" % (station,instrument))


                wr("""<tr><td colspan=2>          Save Current Position As:
                <input type='text'   name='newpos_name' value='' size=35/>
                <input type='submit' name='save_position' value='Save'/></td><tr>
                <tr><td colspan=2> Look up position by date:
                <input type='text' width=33 id='date' name='date' value='%s'/>
                <button id='date_trig'>...</button>
                <button id='date_search' name='search_position' value='Search'>Search</button> </td></tr>
                <tr><td colspan=2>&nbsp;</td></tr>
                """ % (tformat(time.time(),format="%Y-%m-%d %H:%M:%S")))

                wr(jscal_get_date)

                if len(positions)==0:
                    wr("<tr><td colspan=2 align='center'> No saved positions </td></tr>")
                else:
                    wr("""
                    <tr><td colspan=2><hr></td></tr>
                    <tr><td colspan=2>Saved Positions:
                    (<a href='%s/manage_positions?inst_id=%i'>Manage Positions</a>)</td></tr>
                    <tr><td>Name</td><td>Time Saved</td></tr>""" % (mainpage,inst_id))

                    for p in positions:
                        plink = "<a href='%s/view_position?inst=%i&position=%s'>%s" % (mainpage,inst_id,p[1],p[1])
                        wr("<tr><td>%s </td><td>%s</td></tr>" % (plink,tformat(p[2],format="%Y-%m-%d %H:%M:%S")))


                wr("""<tr><td colspan=2><hr></td></tr><tr><td colspan=2>PVs in instrument:
                (<a href='%s/modify_instrument?inst_id=%i'>View/Change)</td></tr>"""
                   % (mainpage,inst_id))

                ix = 0
                for pvn in pvlist:
                    self.write('<td><a href="%s?pv=%s">%s</a></td>'% (pvinfopage,pvn,pvn))
                    ix = ix + 1
                    if ix % 2 == 0: wr("</tr><tr>")
                    

            wr("</table>")
        self.endform()
        self.endhtml()
        return self.get_buffer()
        
                
    def manage_positions(self,**kw):
        ' view details of positions saved for an instrument '

        wr = self.write

        mykw = {'inst_id':'-1'}
        mykw.update(kw)

        
        inst_id = int(mykw['inst_id'])
        
        if mykw.has_key('submit'):
            for k,v in mykw.items():
                hide = ('hidden' == v and k not in (None,''))
                self.arch.hide_position(inst_id=inst_id,name=k,hide=hide)
                if 'remove' == v and k not in (None,''):
                    self.arch.delete_position(inst_id=inst_id,name=k)                    

        positions = self.arch.get_positions(inst_id=inst_id,get_hidden=True)
        instrument,station =  self.arch.get_instrument_names_from_id(inst_id)

        self.starthtml()
        self.show_links(active_tab='Instruments')
        flink = "%s/manage_positions?inst_id=%i" % (mainpage,inst_id)


        if DEBUG: self.show_dict(mykw)

        wr("""<form action ='%s' name='inst_form' enctype='multipart/form-data'  method ='POST'>
        <h3> Positions for Instrument  %s in Station %s </h3><table>
        <tr><td align='center'> Position Name &nbsp; &nbsp; &nbsp; </td>
        <td align='center'> &nbsp;  Time Saved &nbsp; &nbsp;</td>
        <td align='center'> Status </td></tr>
        <tr><td colspan =3 ><hr></td></tr>""" % (flink,instrument,station))

        for p in positions:
            pname = p[1]
            ptime = tformat(p[2], format="%Y-%m-%d %H:%M:%S") + ' &nbsp; &nbsp; &nbsp; '

            cshow,chide = ("checked='true'",'')
            if p[3] =='no': cshow,chide = ('',"checked='true'")
            
            wr("""<tr><td>%s</td><td align='center'>%s</td><td>
            <input type='radio' %s name='%s' value='active'>active 
            <input type='radio' %s name='%s' value='hidden'>hidden
            <input type='radio'    name='%s' value='remove'>delete forever
            </td>
            </tr>""" % (pname,ptime,cshow,pname,chide,pname,pname))
        
        wr("""<tr><td colspan =3 ><hr></td></tr>
        <tr><td><input type='submit' name='submit' value='Update Positions'></td>
        <td colspan=2>
        <a href='%s?station=%s&instrument=%s'>View Positions for %s</a>
        </td></tr></table>""" % (instpage,station,instrument,instrument))

        
        self.endhtml()
        return self.get_buffer()    


    def view_position(self,**kw):
        ' view details of a saved position '

        wr = self.write

        mykw = {'inst':'','position':self.POS_DATE,'desc':'','date':'-1'}
        mykw.update(kw)

        
        inst_id = mykw['inst']
        if inst_id == '': inst_id = '0'
        inst_id = int(inst_id)

        date = int(mykw['date'])

        instrument,station = self.arch.get_instrument_names_from_id(inst_id)
        position = mykw['position']
        if position == self.POS_DATE and date > 0:
            pv_vals,save_time = self.arch.get_instrument_values(inst_id=inst_id,ts=date)
            pname = 'Position' 
        else:
            pv_vals,save_time = self.arch.get_instrument_values(inst_id=inst_id,position=position)
            pname = 'Position %s ' % position
            
        save_ctime = tformat(save_time,format="%Y-%m-%d %H:%M:%S")

        if mykw.has_key('submit'):
            form = 'plain'
            if mykw['submit'].startswith('IDL'):
                form = 'idl'
            elif mykw['submit'].startswith('Python'):
                form = 'py'
            
            if position == self.POS_DATE: position = '(not named : retrieved by date)'
            headers = ["station / instrument: %s / %s" % (station,instrument),
                       "position name: %s " % position,
                       "saved: %s " % save_ctime]
            wr(write_saverestore(pv_vals,format=form,header=headers))
            return self.get_buffer()

        elif mykw.has_key('save_position') and mykw.has_key('newpos_name') and date>0:
            try:
                inst_id = int(mykw['inst'])
            except:
                inst_id = -1
            position =clean_input(mykw['newpos_name'].strip())
            self.arch.save_instrument_position(inst_id = inst_id, name=position, ts=date)

            pname = 'Position %s ' % position
            
        self.starthtml()
        self.show_links(active_tab='Instruments')
        # self.show_dict(mykw)
        
        flink = "%s/view_position?inst=%i&position=%s&date=%i" % (mainpage,inst_id,position,save_time)
        wr("""<form action ='%s' enctype='multipart/form-data'  method ='POST'>
        <h3> %s for Instrument %s / Station %s<p> Position Saved    %s </h3><table>
        <tr><td> PV Name</td> <td> Saved Value </td><td> Current Value </td></tr>
        <tr><td colspan =3 ><hr></td></tr>""" % (flink,pname,instrument,station,save_ctime))
        
        for pvname,val in pv_vals:
            curval  = 'Unknown'
            cacheval =  self.arch.cache.select_one(where="pvname='%s'"%pvname)
            if cacheval.has_key('value'):  curval = str(cacheval['value'])
            wr("<tr><td width=20%% >%s</td><td width=30%% >%s</td><td width=30%% >%s</td></tr>" % (pvname,str(val),curval))

        wr("<tr><td colspan =3 ><hr></td></tr></table>")

        if pname == 'Position':  #(this is an unsaved position!)
            wr("""Save this position as:
            <input type='text'   name='newpos_name' value='' size=35/>
            <input type='submit' name='save_position' value='Save'/><p>""")

        wr("""To restore to these settings, select one of these output formats:<p>
        <input type='submit' name='submit' value='IDL script'>
        <input type='submit' name='submit' value='Python script'>
        <input type='submit' name='submit' value='Save/Restore file'><p>
        and run the script. <br>
        <a href='%s?station=%s&instrument=%s'>View All Positions for %s</a>""" % (instpage,
                                                                                  station,
                                                                                  instrument,
                                                                                  instrument))

        
        self.endhtml()
        return self.get_buffer()    

    def add_station(self,**kw):
        ' form to add a station'
        mykw = {'name':'','submit':'','desc':''}
        mykw.update(kw)

        self.starthtml()
        self.show_links(active_tab='Instruments')
        wr = self.write

        if DEBUG: self.show_dict(mykw)
        
        if mykw['submit'] != '':
            sname = clean_input(mykw['name']).strip()
            sdesc = clean_input(mykw['desc']).strip()            
            if len(sname)>1:
                self.arch.create_station(name=sname,notes=sdesc)

        wr('<form action ="%s/add_station" enctype="multipart/form-data"  method ="POST"><p>' % (mainpage))
        wr("Add a new station:<p>")
        wr("""<table> <tr> <td>Station Name</td>
                           <td><input type='text' name='name'  value='' size=20></td></tr>
                      <tr> <td>Description</td>
                           <td><input type='text' name='desc'  value='' size=60></td></tr>""")
        
        wr("""<tr><td colspan=2> &nbsp;</td></tr>""")
        wr("<tr><td><input type='submit' name='submit' value='Add'></td></tr></table> <hr>")
        
        wr("Currently Defined Stations:<p>")
        self.stations = {}
        for s in self.arch.list_stations():
            self.stations[s['name']] = (s['id'],s['notes'])

        station_list = self.stations.keys() ; station_list.sort()
        wr("<table><tr><td>Name</td><td>Description</td></tr><tr><td colspan=2><hr></td></tr")
        for s in station_list:
            wr("<tr><td>&nbsp;%s &nbsp;&nbsp;</td><td>&nbsp;%s</td></tr>" % (s,self.stations[s][1]))
        wr("</table>")
        self.endhtml()
        return self.get_buffer()    


    def add_instrument(self, **kw):
        ' form to add an instrument'

        mykw = {'name':'','submit':'','desc':'','pv1':'','pv2':'','pv3':'','station':'','form_station':''}
        mykw.update(kw)
        station = mykw['station']
        
        formstation = mykw['form_station'].strip()
        if station == '' and formstation != '':  station = formstation
        
        mykw['station'] = station
       
        self.starthtml()
        self.show_links(help='instruments',active_tab='Instruments')

        wr = self.write

        if DEBUG: self.show_dict(mykw)
        
        if mykw['submit'] != '':
            sname = clean_input(mykw['name']).strip()
            sdesc = clean_input(mykw['desc']).strip()            
            if len(sname)>1:
                self.arch.create_instrument(name=sname,station=station,notes=sdesc)
            pvlist = []
            for k,v in mykw.items():
                if k.startswith('pv') and (v != '' and v is not None):
                    pvlist.append(clean_input(v).strip())
            self.arch.set_instrument_pvs(pvlist,name=sname,station=station)
            wr(" added instrument !! %s " % (sname))

        wr('<form action ="%s/add_instrument" enctype="multipart/form-data"  method ="POST"><p>' % (mainpage))
        wr('<input type="hidden" name="form_station"  value="%s">' % station)
        wr("""Add a new instrument to station '%s' """ % station)
        wr("""<table><tr><td> Instrument Name:</td><td><input type='text'   name='name'  value='' size=35></td></tr>
        <tr><td> Description:</td><td><input type='text'   name='desc'  value='' size=35></td></tr>
        <tr><td> &nbsp; </td><td></td></tr>
        <tr><td colspan=2> Includes the following PVs </td></tr>""")

        for i in range(12):
            self.write("""<tr><td> PV &nbsp;</td><td>
            <input type="text" name="pv%i" value="" size=35></td></tr>""" % i)

        wr("<tr><td colspan=2><input type='submit' name='submit'  value='Add Instrument'></td></tr>")
        
        wr("</table> Note:  you can add more PVs or change the Instrument definition here.")

        self.endhtml()
        return self.get_buffer()

    def modify_instrument(self,**kw):
        ' form to add an instrument'

        inst_id = 0
        mykw = {'station':'','instrument':'','submit':'', 'form_id':0,'inst_id':inst_id}
        mykw.update(kw)

        if mykw['inst_id'] != 0:
            inst_id = int( mykw['inst_id'] )
        else:
            tmp = int(mykw['form_id'].strip())
            if tmp != 0: inst_id = tmp

        if inst_id == 0 and mykw['instrument'] != '' and mykw['station'] != '':
            inst_id = self.arch.get_instrument_id(name=mykw['instrument'],
                                                 station=mykw['station'])

        instrument,station = self.arch.get_instrument_names_from_id(inst_id)

        self.starthtml()
        self.show_links(help='instruments',active_tab='Instruments')

        wr = self.write
        
        if mykw['submit'] != '':
            sname = clean_input(mykw['name']).strip()
            if sname != instrument and sname != '':
                self.arch.instruments.update(name=sname,where="id=%i" % inst_id)

            sdesc = clean_input(mykw['desc']).strip()            
            if sdesc != '':
                self.arch.instruments.update(notes=sdesc,where="id=%i" % inst_id)
            
            # add and remove pvs as directed
            pvs_add = []
            pvs_del = []
            for k,v in mykw.items():
                if 'remove' == v:
                    pvs_del.append(k)
                elif k.startswith('_addpv_') and len(v) >0:
                    pvs_add.append(clean_input(normalize_pvname(v)))
                    
            if len(pvs_del)>0:
                self.arch.remove_instrument_pvs(pvs_del, name=instrument, station=station)

            if len(pvs_add)>0:
                self.arch.set_instrument_pvs(pvs_add, name=instrument, station=station)                


        info   = self.arch.get_instruments(name=instrument,station=station)[0]
        pvlist = self.arch.get_instrument_pvs(name=instrument,station=station)
        pvlist.sort()        

        wr('<form action ="%s/modify_instrument" enctype="multipart/form-data"  method ="POST"><p>' % (mainpage))
        wr('<input type="hidden" name="form_id"  value="%s">' % inst_id)
        wr("<h3>Definition for Instrument: %s      &nbsp;  &nbsp; in Station %s</h3> " % (instrument,station))

        wr("""<table><tr><td> Instrument Name:</td><td><input type='text'   name='name'  value='%s' size=35></td></tr>
        <tr><td> Description:</td><td><input type='text'   name='desc'  value='%s' size=35></td></tr>
        <tr><td> &nbsp; </td><td></td></tr>
        <tr><td colspan=2> Current PVs in instrument: </td><td></td></tr>
        """ % (instrument,info['notes']))
        
        for pvn in pvlist:
            self.write("""<tr><td>%s</td><td>
            <input type='radio'                name='%s' value='remove'>remove 
            <input type='radio' checked='true' name='%s' value='keep'>keep</td></tr>""" % (pvn,pvn,pvn))
        
        wr("<tr><td colspan=2> <hr> </td></tr> <tr><td colspan=2> Add PVs </td></tr>")
        for i in range(4):
            self.write("""<tr><td> PV &nbsp;</td><td>
            <input type="text" name="_addpv_%i" value="" size=35></td></tr>""" % i)

        wr("""<tr><td><input type='submit' name='submit' value='Update Definition'></td>
        <td><a href='%s?station=%s&instrument=%s'>View Positions for %s</a></td>
        </tr></table>""" % (instpage,station,instrument,instrument))

        self.endhtml()
        return self.get_buffer()

    def show_station_choices(self):
        # stations:
        wr = self.write
        self.stations = {}

        
        self.startform(action=instpage)

        self.write("""<script type='text/javascript'>
        function showStation(dropdown) {
           var index=dropdown.selectedIndex;
           var val  = dropdown.options[index].value;
           var url  = '%s';
           var url  = url.concat('?station=');
           var url  = url.concat(val);           
           top.location.href = url;
           }
        </script>"""  % (instpage))
        
        for s in self.arch.list_stations():
            self.stations[s['name']] = (s['id'],s['notes'])

        station_list = self.stations.keys() ; station_list.sort()

        wr("""<font class='h3font'>Station:</font>
        <select id='station' name='station' onChange='showStation(this.form.station);'>""")
        
        for s in station_list:
            extra = ''
            if self.kw['station'] == s: extra = 'selected'
            wr("<option %s value='%s'>%s" % (extra, s, s))
        wr("""</select> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<a href='%s/add_station'>&lt;add a station&gt;</a></form><hr>""" % mainpage)
        
