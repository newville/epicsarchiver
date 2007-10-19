from EpicsArchiver import Archiver, config, add_pv_to_cache
from EpicsArchiver.util import clean_string, clean_input, normalize_pvname

from HTMLWriter import HTMLWriter

DEBUG = False

cgiroot    = config.cgi_url

thispage   = "%s/viewer.py" % cgiroot
adminpage  = "%s/admin.py" % cgiroot
pvinfopage = "%s/admin.py/pvinfo"       % cgiroot
relpv_page = "%s/admin.py/related_pvs"  % cgiroot
instspage  = "%s/instruments.py"  % cgiroot
statuspage = "%s/status.py" % cgiroot

class WebAdmin(HTMLWriter):
    def __init__(self, arch=None, **kw):
        HTMLWriter.__init__(self)
        self.html_title = "PV Archive Admin Page"
        self.arch    = arch or Archiver()
        self.master  = self.arch.master

        self.kw  = {'form_pv':'', 'pv':'',
                    'submit': '','description':'','deadtime':'','deadband':'','type':''}
        self.kw.update(kw)

    def setup_keywords(self,**kw):
        self.kw.update(kw)
        pvname = self.kw['pv'].strip()
        if pvname == '' and self.kw['form_pv'].strip() != '':
             pvname = self.kw['form_pv']
        self.kw['form_pv']  = pvname
        pvn = normalize_pvname(pvname)
        
        self.starthtml()
        self.show_links(pv=pvn)

        if DEBUG: self.show_dict(self.kw)
        return pvn,self.write
        
    def show_adminpage(self,**kw):
        pvname, wr = self.setup_keywords(**kw)

        astat = "<br>&nbsp;&nbsp;&nbsp; ".join(self.master.arch_report())
        cstat = "<br>&nbsp;&nbsp;&nbsp; ".join(self.master.cache_report(brief=True))

        wr("""Archive Status:<br>&nbsp;&nbsp;&nbsp;  %s<br>
           <p>Cache Status:<br>&nbsp;&nbsp;&nbsp;  %s<br><hr>""" % (astat,cstat))
            
        submit = self.kw['submit'].strip()

        if submit.startswith('Add') and len(pvname)>1:
            sx = clean_input(pvname)

            wr("<p>Adding %s to archive!!<p><hr>" % (sx))
            add_pv_to_cache(sx)
            self.kw['submit'] = ''
            self.kw['form_pv'] = ''
            pvname = ''
            self.endhtml()
            return self.get_buffer()
        
        wr("""<form action ='%s' enctype='multipart/form-data' method='POST'><p>
        <p>Search for PV:&nbsp;&nbsp;&nbsp;
        <input type='text' name='form_pv' value='%s' size=40> &nbsp; (use \'*\' for wildcard searches)
        <input type='submit' name='submit' value='Search Archive'><p>"""
           % (adminpage,pvname))
        
        if pvname != '':
            i = 0
            sx = clean_input(pvname.replace('*','%'))
            results = self.master.cache.select(where="pvname like '%s' order by pvname" % sx)
            
            wr("<p>Search results for '%s' (%i matches): </p><table><tr>" % (pvname,len(results)))

            for r in results:
                wr("<td><a href='%s?pv=%s'>%s</a>&nbsp;&nbsp;</td>"%(pvinfopage,r['pvname'],r['pvname']))
                i  = i + 1
                if i % 4 == 0: wr("</tr><tr>")

            wr("</table>")

            if len(results)== 0 and sx.find('%')==-1:
                wr("<input type='submit' name='submit' value='Add %s to Archive'><p>" % pvname)
                   
        self.endhtml()
        return self.get_buffer()

    def show_pvinfo(self,**kw):
        pvname, wr = self.setup_keywords(**kw)

        submit = self.kw['submit'].strip()
        es  = clean_string

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
                
            wr('<p> <a href="%s?pv=%s">Plot %s</a>&nbsp;&nbsp;</p>'% (thispage,pvname,pvname))
            self.endhtml()
            return self.get_buffer()
        if pvname in (None,''):
            wr("No PV given???  Click <a href='%s'>here</a> for Main Admin Page" % adminpage)
            self.endhtml()
            return self.get_buffer()            

        ret = self.arch.pv_table.select(where="name='%s'" % pvname)
        if len(ret)== 0:
            wr("PV not in archive??")
            self.endhtml()
            return self.get_buffer()            

        d = ret[0]
        
        wr("""<p> <h4> %s &nbsp;&nbsp;&nbsp;&nbsp;
        <a href='%s?pv=%s'>Show Plot</a></h4></p>""" % (pvname,thispage,pvname))

        wr("""<form action ='%s' enctype='multipart/form-data'  method='POST'><p>
        <input type='hidden' name='form_pv' value='%s'>
        <table><tr><td colspan=2><hr></td></tr><tr>
        <td>Data Type:</td><td>%s</td></tr><td>Actively Archived:</td><td>
        """ % (pvinfopage,pvname,d['type']))
        
        for i in ('Yes','No'):
            sel = ''
            if i.lower() == d['active'].lower():  sel = "checked=\"true\""
            wr('<input type="radio" %s name="active" value="%s">&nbsp;%s' % (sel,i,i))

        wr("""</td></tr><td> Description:</td><td><input type='text' name='desc' value='%s' size=30>
        </td></tr><tr><td>   Deadtime (seconds):</td><td><input type='text' name='deadtime' value='%s' size=30>
        </td></tr><tr><td>   Deadband (fraction):</td><td><input type='text' name='deadband' value='%s' size=30>
        </td></tr><tr><td>   Graph Upper Limit:</td><td><input type='text' name='graph_hi' value='%s' size=30> 
        </td></tr><tr><td>   Graph Lower Limit:</td><td><input type='text' name='graph_lo' value='%s' size=30>
        </td></tr><tr><td>   Graph Type</td><td>
        """ % (d['description'],str(d['deadtime']),str(d['deadband']),str(d['graph_hi']),str(d['graph_lo'])))

        for i in ('normal','log','discrete'):
            sel = ''
            if i.lower() == d['graph_type'].lower():  sel = "checked='true'"
            wr("<input type='radio' %s name='graph_type' value='%s'>&nbsp;%s" % (sel,i,i))

        wr("""</td></tr><tr><td><input type='submit' name='submit' value='Update PV Settings'></td><td></td></tr>
        <tr><td colspan=2><hr></td></tr></table>""")
        
        self.master.use_master()
        #  Related PVs
        r = self.master.get_related_pvs(pvname)
        i = 0
        if len(r)==0:
            wr("<h4>No Related PVs:  <a href=%s?pv=%s>View and Change</a></h4> <table><tr>" % (relpv_page,pvname))
        else:
            wr("<h4>Related PVs: <a href=%s?pv=%s>View and Change</a></h4> <table><tr>" % (relpv_page,pvname))
            for pv2 in r:
                wr('<td><a href="%s?pv=%s">%s</a>&nbsp;&nbsp;</td>'% (pvinfopage,pv2,pv2))
                i  = i + 1
                if i % 5 == 0: wr("</tr><tr>")
                
            wr("</tr></table>")
        
            
        #  Instruments PVs
        instpage   = "%s/instruments.py"  % cgiroot
        
        r = self.master.get_instruments_with_pv(pvname)
        if len(r)==0:
            wr("<p>No Instruments contain %s</p>" % pvname)
        else:
            wr("<h4>Instruments containing %s:</h4><table><tr>" % pvname)
            for inst_id,inst,station in r:
                ilink = "<a href='%s?station=%s&instrument=%s'>%s</a>" % (instpage,station,inst,inst)
                wr('<td>&nbsp; &nbsp; %s &nbsp;&nbsp;</td>'% (ilink))
                i  = i + 1
                if i % 3 == 0: wr("</tr><tr>")
                
            wr("</tr></table>")
            
        # Alerts:
        wr("<h4>Alerts for %s:</h4><table><tr>" % pvname)
            

        self.endhtml()
        return self.get_buffer()

    def show_related_pvs(self,**kw):
        pvname, wr = self.setup_keywords(**kw)

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
            wr('<form action ="%s?pv=%s" enctype="multipart/form-data"  method ="POST"><p>' % (relpv_page,pvname))
            wr('<input type="hidden" name="form_pv" value="%s">' % pvname)

            r = self.master.get_related_pvs(pvname)
            i = 0
            wr("<h4>Related PVs for &nbsp; &nbsp; %s:</h4> <table cellpadding=2 border=0> " % pvname)

            if len(r)==0:
                wr("<tr><td colspan=4>no Related PVs for %s</td></tr>" % pvname)
            else:
                wr("""<tr><td>PV </td><td>Current Score</td><td></td><td colspan=2>Change Score</td></tr>
                <td colspan=5><hr></td><td></td></tr>""")
                for pv2 in r:
                    score = get_score(pv2,pvname)                    
                    wr("""<tr><td>  %s &nbsp;</td><td>&nbsp; %i</td><td>
                    <input type='radio' name='%s' value='setval_%i'>&nbsp;+5&nbsp;
                    <input type='radio' name='%s' value='setval_%i'>&nbsp;+2&nbsp;</td><td>
                    <input type='radio' name='%s' value='setval_%i'>&nbsp;-2&nbsp;                    
                    <input type='radio' name='%s' value='setval_%i'>&nbsp;-5&nbsp;</td><td>
                    <input type='radio' name='%s' value='setval_%i'>&nbsp;no change
                    <input type='radio' name='%s' value='setval_%i'>&nbsp;set to 0</td></tr>
                    """ % (pv2,score,pv2,score+5,pv2,score+2,pv2,score-2,pv2,score-5,pv2,score,pv2,0))

                wr("<tr><td colspan=5><hr></td></tr>")
            
            for i in range(3):
                wr("""<tr><td>Add related PV &nbsp;</td><td colspan=4>
                <input type="text" name="pv%i" value="" size=30></td></tr>""" % i)

            wr("""<tr><td colspan=5><hr></td></tr><tr><td colspan=2>
            <input type='submit' name='submit' value='Update Relate PVs'></td></tr></table>""")

        self.endhtml()
        return self.get_buffer()


