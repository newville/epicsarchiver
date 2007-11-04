from EpicsArchiver import MasterDB, Archiver, config
from EpicsArchiver.util import clean_string, clean_input, normalize_pvname

from HTMLWriter import HTMLWriter

DEBUG = False

cgiroot    = config.cgi_url
thispage   = "%s/viewer.py" % cgiroot
adminpage  = "%s/admin.py" % cgiroot
pvinfopage = "%s/admin.py/pvinfo"      % cgiroot
relpv_page = "%s/admin.py/related_pvs" % cgiroot
alerts_page = "%s/admin.py/alerts"   % cgiroot

class WebAdmin(HTMLWriter):
    html_title = "PV Archive Admin Page"
    
    def __init__(self, dbconn1=None, dbconn2=None,**kw):
        HTMLWriter.__init__(self)

        self.arch    = Archiver(dbconn=dbconn1)
        self.master  = MasterDB(dbconn=dbconn2) 

        self.arch.db.get_cursor()
        self.master.db.get_cursor()
        
        self.kw  = {'form_pv':'', 'pv':'', 'inst_id':-1,'submit':''}
        self.kw.update(kw)

    def show_adminpage(self,**kw):
        self.setup(formkeys=('pv',), helpsection='main', **kw)
        wr = self.write

        pvname = self.kw['pv']
        astat = "<br>&nbsp;&nbsp;&nbsp; ".join(self.master.arch_report())
        cstat = "<br>&nbsp;&nbsp;&nbsp; ".join(self.master.cache_report(brief=True))
        wr("""Archive Status:<br>&nbsp;&nbsp;&nbsp;  %s<br>
           <p>Cache Status:<br>&nbsp;&nbsp;&nbsp;  %s<br><hr>""" % (astat,cstat))
            
        submit = self.kw['submit'].strip()
        if submit.startswith('Add') and len(pvname)>1:
            pvn = clean_input(pvname)
            wr("<p>Added %s to archive!!<p><hr>" % (pvn))
            self.master.add_pv(pvn)
            #             self.endhtml()
            #             return self.get_buffer()
        
        self.startform(action=adminpage)

        # alertlink = self.link(link="%s/list_alerts" % (adminpage), text='Show All Alerts')
        # wr("<p><b>%s</b></p>" % alertlink)
        wr("""<p>Search for PV:&nbsp;&nbsp;&nbsp;
        %s &nbsp; (use \'*\' for wildcard searches) %s
        """ % (self.textinput(name='form_pv',value=pvname,size=40),
               self.button(text='Search Archive')))
        
        if pvname != '':
            sx = clean_input(pvname.replace('*','%'))
            results = self.master.cache.select(where="pvname like '%s' order by pvname" % sx)
           
            wr("<p>Search results for '%s' (%i matches): </p>" % (pvname,len(results)))
            self.starttable(ncol = 4)

            o = [self.link(link="%s?pv=%s" % (pvinfopage,r['pvname']),text=r['pvname']) for r in results]

            nrows,nextra = divmod(len(results),4)
            for i in range(4): o.append('')
            if nextra>0:  nrows = nrows + 1

            for i in range(nrows):
                self.addrow("&nbsp;%s&nbsp;" % o[0+i*4], "&nbsp;%s&nbsp;" % o[1+i*4],
                            "&nbsp;%s&nbsp;" % o[2+i*4], "&nbsp;%s&nbsp;" % o[3+i*4])
                
            self.endtable()
            if len(results)== 0 and sx.find('%')==-1:
                wr("%s <p>" % self.button(text="Add %s to Archive" % pvname))

        self.endform()
        self.endhtml()
        return self.get_buffer()

    def show_pvinfo(self,**kw):
        self.setup(formkeys=('pv',), helpsection='main', **kw)

        wr = self.write
        pvname = self.kw['pv']
        submit = self.kw['submit'].strip()

        self.master.use_current_archive()
        if submit.startswith('Update') and len(pvname)>1:
            pv_update = self.arch.pv_table.update
            wr("<p>Updating data for %s!!<p><hr>" % (pvname))
            desc  = clean_input(self.kw['description'].strip())
            where = "name='%s'" % (pvname)
            pv_update(where=where, description=desc)
                                                                                   
            kws = {}
            for key in ('description', 'graph_hi', 'graph_lo', 'deadtime',
                        'deadband', 'active', 'graph_type'):
                if self.kw.has_key(key):
                    val = clean_input(self.kw[key].strip()).lower()
                    if key in ('active','graph_type'):
                        if val != '':
                            kws[key] = val
                    else:
                        try:
                            kws[key] = float(val)
                        except:
                            pass

            if len(kws)>0:
                for k,v in kws.items():  wr("<p> update    %s :: %s </p>"  % (k,v))
                pv_update(where=where, **kws)
                
            wr("<p>%s&nbsp;&nbsp;</p>" % self.link(link="%s?pv=%s" % (thispage,pvname),
                                                   text=pvname))
            self.master.use_master()
            self.endhtml()
            return self.get_buffer()

        if pvname in (None,''):
            wr("No PV given???  Click %s for Main Admin Page" % self.link(link=adminpage,
                                                                          text='here'))
            self.endhtml()
            return self.get_buffer()            

        ret = self.arch.pv_table.select(where="name='%s'" % pvname)
        if len(ret)== 0:
            wr("PV not in archive??")
            self.endhtml()
            return self.get_buffer()            

        d = ret[0]
        wr("""<p> <h3> %s &nbsp;&nbsp;&nbsp;&nbsp; %s </h3></p>
        """ % (pvname, self.link(link="%s?pv=%s" % (thispage,pvname),text='Show Plot')))

        self.startform(action=pvinfopage,hiddenkeys=('pv',))
        self.starttable(ncol=2)
        self.addrow('<hr>',spans=(2,0))
        self.addrow("Data Type",d['type'])

        radios =[]
        for i in ('Yes','No'):
            checked = i.lower() == d['active'].lower()
            radios.append( self.radio(checked=checked, name='active',value=i) )
            
        self.addrow("Actively Archived:",  " ".join(radios))
        self.addrow("Description",         self.textinput(name='description',value=d['description']))
        self.addrow("Deadtime (seconds)",  self.textinput(name='deadtime',value=d['deadtime']))
        self.addrow("Deadband (fraction)", self.textinput(name='deadband',value=d['deadband']))
        self.addrow("Graph Upper Limit",   self.textinput(name='graph_hi',value=d['graph_hi']))
        self.addrow("Graph Lower Limit",   self.textinput(name='graph_lo',value=d['graph_lo']))

        radios = []
        for i in ('normal','log','discrete'):
            checked =  i.lower() == d['graph_type'].lower()
            radios.append(self.radio(checked=checked, name='graph_type',value=i))

        self.addrow("Graph Type",          " ".join(radios))
        self.addrow(self.button(text='Update PV Settings'), "")
        self.addrow('<hr>',spans=(2,0))        
        self.endtable()
                
        self.master.use_master()
        #  Related PVs
        related_pvs = self.master.get_related_pvs(pvname)

        if len(related_pvs)==0:
            wr("<hr><h3>No Related PVs: (%s)" % self.link(link="%s?pv=%s" % (relpv_page,pvname),
                                                        text='View/Change'))
        else:
            wr("<hr><h3>Related PVs: (%s)" % self.link(link="%s?pv=%s" % (relpv_page,pvname),
                                                     text='View/Change'))
            self.starttable(ncol=4)

            o = [self.link(link="%s?pv=%s" % (pvinfopage,p),text=p) for p in related_pvs]

            nrows,nextra = divmod(len(related_pvs),4)
            if nextra>0:  nrows = nrows + 1
            for i in range(4): o.append('')
            for i in range(nrows):
                self.addrow("&nbsp;%s&nbsp;" % o[0+i*4], "&nbsp;%s&nbsp;" % o[1+i*4],
                            "&nbsp;%s&nbsp;" % o[2+i*4], "&nbsp;%s&nbsp;" % o[3+i*4])
                
            self.endtable()

        #  Instruments PVs
        instpage   = "%s/instruments.py"  % cgiroot
        
        insts  = self.master.get_instruments_with_pv(pvname)
        if len(insts)==0:
            wr("<hr><h3>No Instruments contain %s</h3>" % pvname)
        else:
            wr("<hr><h3>Instruments containing %s:</h3>" % pvname)
            self.starttable(ncol=4)

            o = []
            for inst_id,inst,station in insts:
                o.append( self.link(link="%s?station=%s&instrument=%s" % (instpage,station,inst),text=inst) )

            nrows,nextra = divmod(len(insts),4)
            if nextra>0:  nrows = nrows + 1
            for i in range(4): o.append('')
            for i in range(nrows):
                self.addrow("&nbsp;%s&nbsp;" % o[0+i*4], "&nbsp;%s&nbsp;" % o[1+i*4],
                            "&nbsp;%s&nbsp;" % o[2+i*4], "&nbsp;%s&nbsp;" % o[3+i*4])
                
            self.endtable()

        # Alerts:
        alerts = self.master.get_alerts(pvname=pvname)
        addlink = self.link(link="%s?pv=%s&new=1" % (alerts_page,pvname),
                            text='Add an Alert')

        if len(alerts)==0:
            wr("<hr><h3>No Alerts set for %s: &nbsp; %s " % (pvname,addlink))
        else:
            wr("<hr><h3>Alerts for %s: %s" % (pvname,addlink))
            self.make_alerttable(pvname,alerts)

        wr("<hr>")
        self.endform()
        self.endhtml()
        return self.get_buffer()

    def make_alerttable(self,pvname,alerts):
        self.starttable(ncol=4,cellpadding=2)
        self.addrow("Label &nbsp;",
                    "&nbsp; Alarm Condition &nbsp;",
                    "&nbsp; Current Status &nbsp;",                         
                    "More Details &nbsp;")
        self.addrow("<hr>", spans=(4,))
            
        for a in alerts:
            link = self.link(link="%s?id=%i" % (alerts_page,a['id']),
                             text='View/Change')

            for tok,desc in zip(self.master.optokens, self.master.opstrings):
                if tok == a['compare']: comp = desc
            compstr = "&nbsp; %s %s" % (comp,a['trippoint'])
            self.addrow("&nbsp; %(name)s "%a, compstr,
                        "&nbsp; %(status)s"%a, link)
        self.addrow("<hr>", spans=(4,))
        self.endtable()
        
    def show_all_alerts(self,**kw):
        self.setup(formkeys=('pv','id'), helpsection='alerts', **kw)        
        self.starttable(ncol=6,cellpadding=2)
        alerts = self.master.get_alerts()

        addlink = self.link(link="%s?new=1" % (alerts_page),text='Add an Alert')

        self.addrow("<h3>All Alerts &nbsp;&nbsp; %s</h3>" % addlink, spans=(5,))
        if len(alerts)== 0:
            self.addrow("<h3>No Alerts Defined &nbsp;&nbsp;&nbsp; %s </h3>"% addlink, spans=(5,))

        self.addrow("<hr>", spans=(6,))

        self.addrow("PV Name &nbsp;","Label &nbsp;",
                    "&nbsp; Alarm Condition &nbsp;",
                    "&nbsp; Status &nbsp;",
                    "&nbsp; Active &nbsp;",
                    "More Details &nbsp;")
        self.addrow("<hr>", spans=(6,))
            
        for a in alerts:
            link = self.link(link="%s?id=%i" % (alerts_page,a['id']),
                             text='View/Change')
            for tok,desc in zip(self.master.optokens, self.master.opstrings):
                if tok == a['compare']: comp = desc
            compstr = "&nbsp; %s %s" % (comp,a['trippoint'])

            self.addrow("&nbsp; %(pvname)s "%a, "&nbsp; %(name)s "%a,
                        compstr, "&nbsp; %(status)s"%a,
                        "&nbsp; %(active)s"%a,  link)
        self.addrow("<hr>", spans=(6,))
        self.endtable()
        self.endhtml()
        return self.get_buffer()

    def show_alerts(self,**kw):
        self.setup(formkeys=('pv','id'), helpsection='alerts', **kw)

        submit = self.kw.get('submit','').strip()
        pvname = self.kw['pv']

        isnew = self.kw.get('new','no') == '1'
        self.kw['new'] = 'no'
        id = int(self.kw.get('id',-1))

        a = {'name':'','pvname':'','compare':'ne','active':'yes',
             'trippoint':0,'id':id,'timeout':'30',
             'mailto':'','mailmsg':self.master.def_alert_msg}
            
        if submit.startswith('Set'):
            a.update(self.kw)
            if isinstance(a['mailto'],(list,tuple)):
                a['mailto'] = ''.join(a['mailto'])
            if isinstance(a['mailmsg'],(list,tuple)):
                a['mailmsg'] = '\n'.join(a['mailmsg'])

            errors = []
            if len(a['name'].strip())<1:      errors.append("Alert Name")
            if len(a['pvname'].strip())<1:    errors.append("PV Name")
            if len(a['mailto'].strip())<1:    errors.append("Mail To Address")
            if len(a['trippoint'].strip())<1: errors.append("Trip Point")

            if len(errors)>0:
                self.write("<h3>Incomplete Information for Alert:</h3>")
                for i in errors:
                    self.write("&nbsp;&nbsp;<font size=+1 color='FF0000'>%s</font>" % i)
            else:

                for tok,desc in zip(self.master.optokens, self.master.opstrings):
                    if desc == a['selection']: a['compare'] = tok

                if int(a['id'])>0: # modify existing alert
                    id = int(a['id'])
                    self.master.update_alert(id=id,
                                             name=a['name'],
                                             pvname=a['pvname'],
                                             active=a['active'].lower(),
                                             mailto=a['mailto'],
                                             mailmsg=a['mailmsg'],
                                             compare=a['compare'],
                                             timeout=a['timeout'],                                             
                                             trippoint=a['trippoint'])
                else: # add new alert
                    self.master.add_alert(name=a['name'],
                                          pvname=a['pvname'],
                                          active=a['active'].lower(),
                                          mailto=a['mailto'],
                                          mailmsg=a['mailmsg'],
                                          compare=a['compare'],
                                          timeout=a['timeout'],
                                          trippoint=a['trippoint'])
                    
        elif submit.startswith('Remove') and id>0:
            self.master.remove_alert(id=id)
            a = {'name':'','pvname':'','compare':'ne','active':'yes',
                 'trippoint':0,'id':id, 'timeout':'30',
                 'mailto':'','mailmsg':self.master.def_alert_msg}
            
        elif id > 0:
            a = self.master.get_alert_with_id(id)
        elif pvname not in ('',None):
            if isnew:
                a['pvname'] = pvname
            else:
                alerts = self.master.get_alerts(pvname=pvname)
                if len(alerts)==1:
                    a = alerts[0]
                else: # show multiple choices
                    self.make_alerttable(pvname,alerts)
                    self.endhtml()
                    return self.get_buffer()

        if not self.kw.has_key('id'): self.kw['id'] = a['id']

        self.startform(action=alerts_page, hiddenkeys=('pv','id'))            

        # normal, show 1 alert....
        if a['mailmsg'] is None:  a['mailmsg'] = self.master.def_alert_msg

        opstr = 'not equal to'
        for tok,desc in zip(self.master.optokens, self.master.opstrings):
            if tok == a['compare']: opstr = desc

        self.starttable(ncol=2)
        title ='Add / Modify Alert'
        if a['pvname'] not in ('',None):
            title = "%s &nbsp; %s" % (title,
                                      self.link(link="%s?pv=%s" % (pvinfopage,a['pvname']),
                                          text='Info for %s'% a['pvname']))

        self.addrow(title, spans=(2,0))
            
        self.addrow('<hr>',spans=(2,0))            
        radios =[]
        for i in ('Yes','No'):
            checked = i.lower() == a['active'].lower()
            radios.append( self.radio(checked=checked, name='active',value=i) )
            
        self.addrow("Alert is Active:",  " ".join(radios))

        self.addrow("Alert Label",      self.textinput(name='name',size=65,
                                                      value=a['name']))
        self.addrow("PV Name",         self.textinput(name='pvname', size=65,
                                                      value=a['pvname']))
        self.addrow("Alert Condition", self.select(name='selection',default=opstr,
                                                   choices=self.master.opstrings))

        self.addrow("Trip Point",     self.textinput(name='trippoint', size=65,
                                                     value=a['trippoint']))

        self.addrow("Time Out (s)",     self.textinput(name='timeout', size=20,
                                                       value=a['timeout']))

        self.addrow("Send Mail To", self.textinput(name='mailto',
                                                   size=65, nlines=4,
                                                   value=a['mailto']))
        self.addrow("Mail Message", self.textinput(name='mailmsg',
                                                   size=65, nlines=8,
                                                   value=a['mailmsg']))

        self.addrow('&nbsp;')
        self.addrow(self.button(text='Set Alert'),
                    self.button(text='Remove This Alert'))
        self.addrow('<hr>',spans=(2,0))                    
        self.endtable()
        self.endform()
        self.endhtml()
        return self.get_buffer()

    def show_related_pvs(self,**kw):
        self.setup(formkeys=('pv',), helpsection='main', **kw)

        wr = self.write
        pvname = self.kw['pv']
        submit = self.kw['submit'].strip()
        
        get_score = self.master.get_pair_score
        set_score = self.master.set_pair_score
        if submit.startswith('Update'):
            if len(kw)>0:
                x   = kw.pop('submit')
                pv1 = kw.pop('form_pv')
                for i in ('pv0','pv1','pv2'):
                    pv2 = kw.get(i,'').strip()
                    if pv2 != '':    set_score(pv1,pv2,10)
                    kw[i] = ''
                for i in ('pv0','pv1','pv2'):
                    kw.pop(i)
                for pv2,action in kw.items():
                    if action.startswith('setval'):
                        set_score(pv1,pv2,int(action[7:]))
                       
        if pvname is not None:
            self.startform(action=relpv_page, hiddenkeys=('pv',))

            related_pvs = self.master.get_related_pvs(pvname)
            i = 0

            if len(related_pvs)==0:
                wr("<h3>No Related PVs for &nbsp; &nbsp; %s</h3>" % pvname)
                self.starttable(ncol=5)                
            else:
                wr("<h3>Related PVs for &nbsp; &nbsp; %s:</h3> " % pvname)
                self.starttable(ncol=5)
                self.addrow("PV","Current Score","Change Score",spans=(1,1,3))
                self.addrow("<hr>",spans=(5,))

                for pv2 in related_pvs:
                    score = get_score(pv2,pvname)                    
                    self.addrow("%s &nbsp;" % pv2,
                                "%i &nbsp;" %score,
                                "%s &nbsp; %s" % (self.radio(name=pv2, value='setval_%i' % (score+5), text='+5'),
                                                  self.radio(name=pv2, value='setval_%i' % (score+2), text='+2')),
                                "%s &nbsp; %s" % (self.radio(name=pv2, value='setval_%i' % (score),   text='no change',checked=True),
                                                  self.radio(name=pv2, value='setval_%i' % (score-2), text='-2')),
                                "%s &nbsp; %s" % (self.radio(name=pv2, value='setval_%i' % (score-5), text='-5'),
                                                  self.radio(name=pv2, value='setval_%i' % 0,         text='set to 0'))
                                )

                self.addrow("<hr>",spans=(5,))
            
            for i in range(3):
                self.addrow("Add related PV &nbsp;",
                            self.textinput(name="pv%i" % i), spans=(1,4))

            self.addrow("<hr>",spans=(5,))
            self.addrow(self.button(text = 'Update Related PVs'), '',spans=(1,4))
            self.endtable()
            self.endform()
            
        self.endhtml()
        return self.get_buffer()
    
