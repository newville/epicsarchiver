from EpicsArchiver import Archiver, config, add_pv_to_cache
from EpicsArchiver.util import clean_string, clean_input, normalize_pvname

from HTMLWriter import HTMLWriter

DEBUG = False

cgiroot    = config.cgi_url
thispage   = "%s/viewer.py" % cgiroot
adminpage  = "%s/admin.py" % cgiroot
pvinfopage = "%s/admin.py/pvinfo"       % cgiroot
relpv_page = "%s/admin.py/related_pvs"  % cgiroot

class WebAdmin(HTMLWriter):
    html_title = "PV Archive Admin Page"
    
    def __init__(self, arch=None, **kw):
        HTMLWriter.__init__(self)

        self.arch    = arch or Archiver()
        self.master  = self.arch.master

        self.kw  = {'form_pv':'', 'pv':'', 'inst_id':-1,'submit':''}
        self.kw.update(kw)

    def show_adminpage(self,**kw):
        self.setup(formkeys=('pv',), **kw)
        wr = self.write

        pvname = self.kw['pv']
        astat = "<br>&nbsp;&nbsp;&nbsp; ".join(self.master.arch_report())
        cstat = "<br>&nbsp;&nbsp;&nbsp; ".join(self.master.cache_report(brief=True))
        wr("""Archive Status:<br>&nbsp;&nbsp;&nbsp;  %s<br>
           <p>Cache Status:<br>&nbsp;&nbsp;&nbsp;  %s<br><hr>""" % (astat,cstat))
            
        submit = self.kw['submit'].strip()
        if submit.startswith('Add') and len(pvname)>1:
            pvn = clean_input(pvname)
            wr("<p>Adding %s to archive!!<p><hr>" % (pvn))
            add_pv_to_cache(pvn)
            self.endhtml()
            return self.get_buffer()
        
        self.startform(action=adminpage)

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
        self.setup(formkeys=('pv',), **kw)

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
        wr("""<p> <h4> %s &nbsp;&nbsp;&nbsp;&nbsp; %s </h4></p>
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
        self.addrow("Description",         self.textinput(name='desc',    value=d['description']))
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
            wr("<h4>No Related PVs: %s" % self.link(link="%s?pv=%s" % (relpv_page,pvname), text='View and Change'))
        else:
            wr("<h4>Related PVs: %s" % self.link(link="%s?pv=%s" % (relpv_page,pvname), text='View and Change'))
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
            wr("<p>No Instruments contain %s</p>" % pvname)
        else:
            wr("<h4>Instruments containing %s:</h4>" % pvname)
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
        wr("<h4>Alerts for %s:</h4>" % pvname)
            
        self.endform()
        self.endhtml()
        return self.get_buffer()

    def show_related_pvs(self,**kw):
        self.setup(formkeys=('pv',), **kw)

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
                    if pv2 != '':  set_score(pv1,pv2,10)
                    kw[i] = ''
                for i in ('pv0','pv1','pv2'): kw.pop(i)
                for pv2,action in kw.items():
                    score = None
                    if action.startswith('setval'):
                        score = int(action[7:])
                    if score is not None:   set_score(pv1,pv2,score)

        if pvname is not None:
            action = "%s?pv=%s" % (relpv_page,pvname)
            self.startform(action=relpv_page, hiddenkeys=('pv',))

            related_pvs = self.master.get_related_pvs(pvname)
            i = 0

            if len(related_pvs)==0:
                wr("<h4>No Related PVs for &nbsp; &nbsp; %s</h4>" % pvname)
                self.starttable(ncol=5)                
            else:
                wr("<h4>Related PVs for &nbsp; &nbsp; %s:</h4> " % pvname)
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
    
