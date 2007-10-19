#!/usr/bin/env python

import time
from EpicsArchiver import InstrumentDB, config

from HTMLWriter import HTMLWriter, jscal_get_date

from util import normalize_pvname, set_pair_scores, clean_input, tformat,write_saverestore
pagetitle  = config.pagetitle
cgiroot    = config.cgi_url
footer     = config.footer
instpage   = "%s/instruments.py"  % cgiroot
pvinfopage = "%s/admin.py/pvinfo" % cgiroot

class WebInstruments(HTMLWriter):
    table_def   = "<table width=90% cellpadding=1 border=0 cellspacing=2>"    
    hrule_row   = "<tr><td colspan=2> <hr>   </td></tr>"
    space_row   = "<tr><td colspan=2> &nbsp; </td></tr>"
    normal_row  = "<tr><td><b>%s</b></td><td>%s</td></tr>"
    colored_row = "<tr><td><b>%s</b></td><td><font color=%s> %s </font></td></tr>"
    title_row   = "<tr><th colspan=2><font color=%s>%s</font></tr>"
    
    def __init__(self,arch=None,**kw):

        HTMLWriter.__init__(self)
        self.arch   = arch or InstrumentDB()

        self.kw  = {'station_sel':'', 'newstation':'',
                    'station':'', 'instrument':'','pv':'',
                    'station_add':'',
                    'submit': 'Select Station'    }

        self.kw.update(kw)
        self.html_title = 'Epics Instruments'

    def show(self,station=None,instrument=None,pv=None,**kw):
        self.kw.update(kw)

        if pv is None:  pv = self.kw['pv'].strip()
        if station is None:  station = self.kw['station'].strip()
        if instrument is None:  instrument = self.kw['instrument'].strip()


        self.kw['pv'] = pv
        self.kw['station'] = station
        self.kw['instrument'] = instrument

        
        self.starthtml()
        self.show_links(pv=pv)

        wr = self.write

        self.show_dict(self.kw)
            
        # finally, draw the full page
        self.draw_page()
            
        self.endhtml()
        return self.get_buffer()
        
    def draw_page(self):
        
        pv = self.kw['pv']
        station = self.kw['station']
        instrument = self.kw['instrument']

        wr = self.write                

        wr(" <h4> Instruments </h4> ")
        wr('<form action ="%s" enctype="multipart/form-data"  method ="POST"><p>' % (instpage))
        wr('<input type="hidden" name="form_pv"   value="%s">' % pv)

        self.show_station_choices()

        if station == '':
            wr("Please select a station.")
        else:
            # a large outer 2 column table: 
            wr("<table cellpadding=2 border=1><tr><td width=30% >")   # left side  : instrument list
            wr("<table><tr><td>Instruments for %s:</td></tr>" % station)
            wr("<tr><td><a href='%s/add_instrument?station=%s'> &lt;add instrument&gt; </a></td></tr>" % (instpage,station))
            
            self.instruments = {}
            for s in self.arch.list_instruments(station=station):
                self.instruments[s['name']] = (s['id'],s['notes'])

            inst_list = self.instruments.keys() ; inst_list.sort()
            
            for inst in inst_list:
                ilink = "<a href='%s?station=%s&instrument=%s'>%s</a>" % (instpage,station,inst,inst)
                wr("<tr><td>%s</td></tr>" % ilink)

            wr("</table></td><td><table align='center'>")   # right side : positions for this instrument
            if instrument == '':
                wr("<tr><td colspan=2>Please select an instrument</td></tr>")
            else:
                inst_id = self.instruments[instrument][0]
                
                positions = self.arch.get_positions(inst=instrument,station=station)
                pvlist    = self.arch.get_instrument_pvs(name=instrument,station=station)
                pvlist.sort()

                wr("<input type='hidden' name='instrument_name'  value='%s'>" % instrument)
                wr("<input type='hidden' name='instrument_id'  value=%i>" % inst_id)
                wr("<tr><td align='center' colspan=2>%s: %s</td></tr>" % (station,instrument))


                wr("""<tr><td colspan=2>          Save Current Position As:
                <input type='text'   name='newpos_name' value='' size=35/>
                <input type='submit' name='save_position' value='Save'/></td><tr>
                <tr><td colspan=2> Look up position by date:
                <input type='text' width=33 id='date' name='date' value=''/>
                <button id='date_trig'>...</button>
                <button id='date_search' name='search_position' value='Search'>Search</button> </td></tr>
                <tr><td colspan=2>&nbsp;</td></tr>""")

                wr(jscal_get_date)
                

                if len(positions)==0:
                    wr("<tr><td colspan=2 align='center'> No saved positions </td></tr>")
                else:
                    wr("""<tr><td colspan=2>Saved Positions:</td></tr>
                    <tr><td colspan=2><hr></td></tr>
                    <tr><td> Name</td><td>Time Saved</td></tr>""")

                    for p in positions:
                        plink = "<a href='%s/view_position?inst=%i&position=%s'>%s" % (instpage,inst_id,p[1],p[1])
                        wr("<tr><td>%s </td><td>%s</td></tr>" % (plink,tformat(p[2],format="%Y-%b-%d %H:%M:%S")))


                wr("""<tr><td colspan=2><hr></td></tr><tr><td colspan=2>PVs in instrument:
                <a href='%s/modify_instrument?inst_id=%i'>View/Change </td></tr>"""
                   % (instpage,inst_id))

                ix = 0
                for pvn in pvlist:
                    self.write('<td><a href="%s?pv=%s">%s</a></td>'% (pvinfopage,pvn,pvn))
                    ix = ix + 1
                    if ix % 2 == 0: wr("</tr><tr>")
                    

            wr("</table>")
           
    def show_dict(self,d):
        for k,v in d.items():
            self.write("%s= '%s' <br> " % (k,v))                    
        
    def view_position(self,**kw):
        ' view details of a saved position '
        mykw = {'inst':'','position':'_(by_date)_','desc':'','date':''}
        mykw.update(kw)

        wr = self.write

        inst_id = mykw['inst']
        if inst_id == '': inst_id = '0'
        inst_id = int(inst_id)

        instrument,station = self.arch.get_instrument_names_from_id(inst_id)
        position = mykw['position']
        if position == '_(by_date)_' and mykw['date'] != '':
            pv_vals,save_time = self.arch.get_instrument_values(position=None,ts=int(date))
            
            
        else:
            positions = self.arch.get_positions(inst_id=inst_id, name=position)[0]
            pv_vals = self.arch.get_position_values(positions)
            save_time  = int(positions[2])

        save_ctime = tformat(save_time,format="%Y-%b-%d %H:%M:%S")


        if mykw.has_key('submit'):
            form = 'plain'
            if mykw['submit'].startswith('IDL'):
                form = 'idl'
            elif mykw['submit'].startswith('Python'):
                form = 'py'
            
            if position == '_(by_date)_': position = '(not named : retrieved by date)'
            headers = ["restore position: %s " % position,
                       "for instrument: %s / station: %s" % (instrument,station),
                       "saved at time: %s " % save_time]
            wr(write_saverestore(pv_vals,format=form,header=headers))
            return self.get_buffer()


        self.starthtml()
        self.show_links()
        flink = "%s/view_position?inst=%i&position=%s&date=%i" % (instpage,inst_id,position,save_time)
        wr("""<form action ='%s' enctype='multipart/form-data'  method ='POST'>
        <h4> Position %s for Instrument %s / Station %s<p> Position Saved    %s </h4><table>
        <tr><td> PV Name</td> <td> Saved Value </td><td> Current Value </td></tr>
        <tr><td colspan =3 ><hr></td></tr>""" % (flink,position,instrument,station,save_ctime))
        
        for pvname,val in pv_vals:
            curval  = 'Unknown'
            cacheval =  self.arch.cache.select_one(where="pvname='%s'"%pvname)
            if cacheval.has_key('value'):  curval = str(cacheval['value'])
            wr("<tr><td width=20%% >%s</td><td width=30%% >%s</td><td width=30%% >%s</td></tr>" % (pvname,str(val),curval))

        wr("<tr><td colspan =3 ><hr></td></tr></table>")

        wr("""To restore to these settings, select one of these output formats:<p>
        <input type='submit' name='submit' value='IDL script'>
        <input type='submit' name='submit' value='Python script'>
        <input type='submit' name='submit' value='Save/Restore file'><p>
           and run the script. """)

        
        self.endhtml()
        return self.get_buffer()    

    def add_station(self,**kw):
        ' form to add a station'
        mykw = {'name':'','submit':'','desc':''}
        mykw.update(kw)

        self.starthtml()
        self.show_links()
        wr = self.write

        # self.show_dict(mykw)
        
        if mykw['submit'] != '':
            sname = clean_input(mykw['name']).strip()
            sdesc = clean_input(mykw['desc']).strip()            
            if len(sname)>1:
                self.arch.create_station(name=sname,notes=sdesc)

        wr('<form action ="%s/add_station" enctype="multipart/form-data"  method ="POST"><p>' % (instpage))
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


    def add_instrument(self,station='',**kw):
        ' form to add an instrument'

        mykw = {'name':'','submit':'','desc':'','pv1':'','pv2':'','pv3':'','station':'','form_station':''}
        mykw.update(kw)
        
        formstation = mykw['form_station'].strip()
        if station == '' and formstation != '':  station = formstation
        
        mykw['station'] = station
       
        self.starthtml()
        self.show_links()

        wr = self.write

        self.show_dict(mykw)
        
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

        wr('<form action ="%s/add_instrument" enctype="multipart/form-data"  method ="POST"><p>' % (instpage))
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
        self.show_links()

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

        wr('<form action ="%s/modify_instrument" enctype="multipart/form-data"  method ="POST"><p>' % (instpage))
        wr('<input type="hidden" name="form_id"  value="%s">' % inst_id)
        wr("<h4>Definition for Instrument: %s      &nbsp;  &nbsp; in Station %s</h4> " % (instrument,station))

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
        
        wr("<table>")
        self.stations = {}
        for s in self.arch.list_stations():
            self.stations[s['name']] = (s['id'],s['notes'])

        station_list = self.stations.keys() ; station_list.sort()
        wr("<tr><td>Station: <select id='station' name='station'>")
        for s in station_list:
            extra = ''
            if self.kw['station'] == s: extra = 'selected'
            wr("<option %s value='%s'>%s" % (extra, s, s))
        wr("""</select>
        <input type='submit' name='station_sel' value='Select Station'></td><td>
        <td>&nbsp;&nbsp;<a href='%s/add_station'>Add Station</a></td><tr>
        <tr><td colspan=4><hr></td></tr></table>""" % (instpage))

        
