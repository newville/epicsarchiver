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

        self.kw  = {'form_pv':'', 'submit': '','description':'','deadtime':'','deadband':'','type':''}
        self.kw.update(kw)

    def show_adminpage(self,pv=''):
        pvname = self.kw['form_pv'].strip()
        if pvname == '' and pv != '':
            pvname = pv
            self.kw['form_pv'] = pvname

        self.starthtml()
        self.show_links(pv=pvname)

        stat = "<br>&nbsp;&nbsp;&nbsp; ".join(self.master.arch_report())
        self.write("Archive Status:<br>&nbsp;&nbsp;&nbsp;  %s<br>" % stat)

        stat = "<br>&nbsp;&nbsp;&nbsp; ".join(self.master.cache_report(brief=True))
        self.write("<p>Cache Status:<br>&nbsp;&nbsp;&nbsp;  %s<br>" % stat)        

        self.write("<hr>")

            
        submit = self.kw['submit'].strip()

        if submit.startswith('Add') and len(pvname)>1:
            sx = clean_input(pvname)
            self.write("<p>Adding %s to archive!!<p><hr>" % (sx))
            add_pv_to_cache(sx)
            self.kw['submit'] = ''
            self.kw['form_pv'] = ''
            pvname = ''
            self.endhtml()
            return self.get_buffer()
        
        self.write('<form action ="%s" enctype="multipart/form-data"  method ="POST"><p>' % (adminpage))
        self.write('<p>Search for PV:&nbsp;&nbsp;&nbsp;')
        self.write('<input type="text" name="form_pv" value="%s" size=40> &nbsp; (use \'*\' for wildcard searches)' % pvname)
        self.write("<input type='submit' name='submit' value='Search Archive'><p>")
        if pvname != '':
            i = 0
            sx = clean_input(pvname.replace('*','%'))

            results = self.master.cache.select(where="pvname like '%s' order by pvname" % sx)

            self.write("<p>Search results for '%s' (%i matches): </p>" % (pvname,len(results)))
            self.write("<table><tr>")

            for r in results:
                self.write('<td><a href="%s?pv=%s">%s</a>&nbsp;&nbsp;</td>'% (pvinfopage,r['pvname'],r['pvname']))
                i  = i + 1
                if i % 3 == 0: self.write("</tr><tr>")

            self.write("</table>")

            if len(results)== 0 and sx.find('%')==-1:
                self.write("<input type='submit' name='submit' value='Add %s to Archive'><p>" % pvname)
                   
        self.endhtml()
        return self.get_buffer()

    def show_pvinfo(self,pv=None,**kw):
        self.kw.update(kw)

        pvname = self.kw['form_pv'].strip()
        if pvname == '' and pv != '':
            pvname = pv
            self.kw['form_pv'] = pvname

        self.starthtml()
        self.show_links(pv=pvname)

        if DEBUG:
            self.write('<p> === Keys: === </p>')
            for key,val in self.kw.items():
                self.write(" %s :  %s <br>" % (key,val))

        if pv is None:
            fpv = self.kw['form_pv'].strip()
            if fpv != '': pv = fpv

        submit = self.kw['submit'].strip()
        es  = clean_string

        self.master.use_current_archive()

        if submit.startswith('Update') and len(pv)>1:
            pv_update = self.arch.pv_table.update
            pvn = clean_input(pv)
            self.write("<p>Updating data for %s!!<p><hr>" % (pvn))
            desc  = clean_input(self.kw['description'].strip())
            where = "name='%s'" % (pvn)
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
                for k,v in kws.items():
                    self.write('<p> update    %s :: %s </p>'  % (k,v))
                pv_update(where=where, **kws)
                
            self.write('<p> <a href="%s?pv=%s">Plot %s</a>&nbsp;&nbsp;</p>'% (thispage,pvn,pvn))
            self.endhtml()
            return self.get_buffer()
        if pv in (None,''):
            self.write("No PV given??")
            self.write("No PV given???  Click <a href='%s'>here</a> for Main Admin Page" % adminpage)

            self.endhtml()
            return self.get_buffer()            

        ret = self.arch.pv_table.select(where="name='%s'" % pv)
        if len(ret)== 0:
            self.write("PV not in archive??")
            self.endhtml()
            return self.get_buffer()            

        pvn = clean_input(pv)
        self.write('<p> <h4> %s    ' % (pvn))
        self.write('  &nbsp;&nbsp;&nbsp;&nbsp; <a href="%s?pv=%s">Show Plot</a></h4></p>' % (thispage,pvn))
        d = ret[0]
        self.write('<form action ="%s" enctype="multipart/form-data"  method ="POST"><p>' % (pvinfopage))
        self.write('<input type="hidden" name="form_pv" value="%s">' % pvn)
        
        self.write("<table><tr><td colspan=2><hr></td></tr><tr>")

        self.write('<td>Data Type:</td><td>%s</td></tr>' % d['type'])
        self.write("<td>Actively Archived:</td><td>")
        for i in ('Yes','No'):
            sel = ''
            if i.lower() == d['active'].lower():  sel = "checked=\"true\""
            self.write('<input type="radio" %s name="active" value="%s">&nbsp;%s' % (sel,i,i))
        self.write("</td></tr>")

        self.write("<td>")        
        self.write('Description:</td><td><input type="text" name="desc" value="%s" size=30></td>' % d['description'])
        self.write("</tr><tr><td>")
        self.write('Deadtime (seconds):</td><td><input type="text" name="deadtime" value="%s" size=30></td>' % str(d['deadtime']))
        self.write("</tr><tr><td>")
        self.write('Deadband (fraction):</td><td><input type="text" name="deadband" value="%s" size=30></td>' % str(d['deadband']))

        self.write("</tr><tr><td>")
        self.write('Graph Upper Limit:</td><td><input type="text" name="graph_hi" value="%s" size=30></td>' % str(d['graph_hi']))
        self.write("</tr><tr><td>")
        self.write('Graph Lower Limit:</td><td><input type="text" name="graph_lo" value="%s" size=30></td>' % str(d['graph_lo']))

        self.write("</tr><tr><td>Graph Type</td><td>")
        for i in ('normal','log','discrete'):
            sel = ''
            if i.lower() == d['graph_type'].lower():  sel = "checked=\"true\""
            self.write('<input type="radio" %s name="graph_type" value="%s">&nbsp;%s' % (sel,i,i))
        self.write("</td></tr>")


        self.write("<tr><td><input type='submit' name='submit' value='Update PV Settings'></td><td></td></tr>")

        self.write("<tr><td colspan=2><hr></td></tr></table>")

        
        self.master.use_master()
        #  Related PVs
        r = self.master.get_related_pvs(pvn)
        i = 0
        if len(r)==0:
            self.write("<h4>No Related PVs:  <a href=%s?pv=%s>View and Change</a></h4> <table><tr>" % (relpv_page,pvn))
        else:
            self.write("<h4>Related PVs: <a href=%s?pv=%s>View and Change</a></h4> <table><tr>" % (relpv_page,pvn))
            for pv2 in r:
                self.write('<td><a href="%s?pv=%s">%s</a>&nbsp;&nbsp;</td>'% (pvinfopage,pv2,pv2))
                i  = i + 1
                if i % 3 == 0: self.write("</tr><tr>")
                
            self.write("</tr></table>")
        
            
        #  Instruments PVs
        r = self.master.get_related_pvs(pvn)
        i = 0
        if len(r)==0:
            self.write("<p>No Instruments for %s</p>" % pvn)
        else:
            self.write("<h4>Instruments: <a href=%s?pv=%s>View and Change</a></h4> <table><tr>" % (relpv_page,pvn))
            for pv2 in r:
                self.write('<td><a href="%s?pv=%s">%s</a>&nbsp;&nbsp;</td>'% (pvinfopage,pv2,pv2))
                i  = i + 1
                if i % 3 == 0: self.write("</tr><tr>")
                
            self.write("</tr></table>")
        
            

        self.endhtml()
        return self.get_buffer()

    def show_related_pvs(self,pv=None,**kw):
        self.kw.update(kw)
        submit = self.kw['submit'].strip()

        pvname = self.kw['form_pv'].strip()
        if pvname == '' and pv != '':
            pvname = pv
            self.kw['form_pv'] = pvname

        self.starthtml()
        self.show_links(pv=pvname)
        
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

        if pv is not None:
            pvn = normalize_pvname(clean_input(pv))

            self.write('<form action ="%s?pv=%s" enctype="multipart/form-data"  method ="POST"><p>' % (relpv_page,pvn))
            self.write('<input type="hidden" name="form_pv" value="%s">' % pvn)

            r = self.master.get_related_pvs(pvn)
            i = 0
            self.write("<h4>Related PVs for &nbsp; &nbsp; %s:</h4> <table cellpadding=2 border=0> " % pvn)

            if len(r)==0:
                self.write("<tr><td colspan=4>no Related PVs for %s</td></tr>" % pvn)
            else:
                self.write("""<tr><td>PV </td><td>Current Score</td><td></td><td colspan=2>Change Score</td></tr>
                <td colspan=5><hr></td><td></td></tr>""")
                for pv2 in r:
                    score = get_score(pv2,pvn)                    
                    self.write("""<tr><td>  %s &nbsp;</td><td>&nbsp; %i</td><td>
                    <input type='radio' name='%s' value='setval_%i'>&nbsp;+5&nbsp;
                    <input type='radio' name='%s' value='setval_%i'>&nbsp;+2&nbsp;</td><td>
                    <input type='radio' name='%s' value='setval_%i'>&nbsp;-2&nbsp;                    
                    <input type='radio' name='%s' value='setval_%i'>&nbsp;-5&nbsp;</td><td>
                    <input type='radio' name='%s' value='setval_%i'>&nbsp;no change
                    <input type='radio' name='%s' value='setval_%i'>&nbsp;set to 0</td></tr>
                    """ % (pv2,score,pv2,score+5,pv2,score+2,pv2,score-2,pv2,score-5,pv2,score,pv2,0))

                self.write("<tr><td colspan=5><hr></td></tr>")
            
            for i in range(3):
                self.write("""<tr><td>Add related PV &nbsp;</td><td colspan=4>
                <input type="text" name="pv%i" value="" size=30></td></tr>""" % i)

            self.write("""<tr><td colspan=5><hr></td></tr><tr><td colspan=2>
            <input type='submit' name='submit' value='Update Relate PVs'></td></tr></table>""")

        self.endhtml()
        return self.get_buffer()


    def show_instruments(self,station=None, instrument=None,pvname=None,**kw):
        self.kw.update(kw)
        submit = self.kw['submit'].strip()        
        self.starthtml()
        self.show_links()        

        self.write("<h4>Instruments Page</hr>")

        self.endhtml()
        return self.get_buffer()

            
