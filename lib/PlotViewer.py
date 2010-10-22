#!/usr/bin/python
import os
import time
import epics

from EpicsArchiver import Archiver, config
from EpicsArchiver.util import SEC_DAY, clean_string, clean_input, \
     normalize_pvname, timehash, time_sec2str, time_str2sec

from EpicsArchiver.HTMLWriter import HTMLWriter, jscal_get_2dates

DEBUG=False
HAS_GNUPLOT = False
plotpage   = "%s/show.py/plot" % config.cgi_url

os.environ['GNUTERM'] = 'png'

try:
    import Gnuplot
    Gnuplot.GnuplotOpts.default_term='png'
    HAS_GNUPLOT = True
except:
    HAS_GNUPLOT = False

class PlotViewer(HTMLWriter):
    ago_times = ('15 minutes', '30 minutes',
                 '1 hour', '2 hours', '3 hours', '6 hours','8 hours','12 hours', 
                 '1 day','2 days','3 days', '1 week', '2 weeks', '1 month')

    years   = range(2001, time.localtime()[0]+1)
    months  = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    days    = (31,28,31,30,31,30,31,31,30,31,30,31)
    minutes = ('00','05','10','15','20','25', '30','35','40','45','50','55')
    file_pref  = config.data_dir
    link_pref  = config.data_url

    gp_base = """set nokey
set term png transparent medium xffffff x000000 xe8e8e8 x0000dd xdd0000 xdd00dd xf2f2f2
set timefmt "%Y%m%d %H%M%S"
set xdata time
set format x "%H:%M\\n%b-%d"
set style line 1 lt 1 lw 3
set style line 2 lt 2 lw 3
set style line 3 lt 3 lw 3
set style line 4 lt 4 lw 1
set grid back ls 4
"""
    gp2_base = """set key
set y2tics
set ytics nomirror
"""
    html_title = "Epics Archiver Data Viewer"
        
    def __init__(self, dbconn=None,  **kw):
        HTMLWriter.__init__(self)

        self.arch   = Archiver(dbconn=dbconn)
        self.arch.db.get_cursor()

        self.dbconn = self.arch.dbconn
        
        self._gp = None
        if HAS_GNUPLOT:  self._gp = Gnuplot.Gnuplot() 
        self.kw  = {'text_pv':'', 'text_pv2':'',  'use_ylog':'', 'use_y2log': '',
                    'submit': '', 'time_ago': '1 day', 
                    'ymin':'', 'ymax':'', 'y2min':'', 'y2max':'',
                    'date1': '', 'date2': ''}
        self.kw.update(kw)
        for i in ('use_ylog', 'use_y2log'):
            if self.kw[i] not in  ('Yes', 'No'):
                self.kw[i] = 'Auto'
                
        if not self.file_pref.endswith('/'): self.file_pref = "%s/" % self.file_pref

    def gp(self,s):
        " simple wrapper around gnuplot "
        self.gpfile.write("%s\n" % s)
        if HAS_GNUPLOT:  self._gp(s)

    def fix_gpfile(self,fname,pattern):
        " simple wrapper around gnuplot "
        self.gpfile.flush()
        self.gpfile.close()
        f = open(fname,'r')
        lines = f.readlines()
        f.close()
        f2 = open(fname,'w')
        for l in lines:
            f2.write( l.replace(pattern,'') )
        f2.close()
        
    def in_database(self,pvname):
        if not pvname: return False
        if pvname == '': return False
        x = pvname
        if x.find('.') == -1: x = "%s.VAL" % x
        return x in self.arch.get_cache_names()
    

    def draw_form(self,pv1='',pv2='',time_ago='',date1='',date2='',**kw):

        action  = self.kw['submit']
        pvname1 = pv1 or ''
        pvname2 = pv2 or ''
        self.write("<table><tr valign='top'><td>")
        self.startform(action=plotpage,name='plot')

        # pv1 = self.argclean(pvname1,  self.kw['text_pv'])

        # self.write("<h3>Epics PV Archive: %s</h3>" % (time.ctime()))

        self.starttable(ncol=6, border=0, cellpadding=1)
        #
        inptext = self.textinput

        self.addrow("PV 1", inptext(name='text_pv', value=pvname1),"",
                    "PV 2", inptext(name='text_pv2',value=pvname2),"")
                    
        self.addrow("PV (Y) range:",
                    "%s:%s" % (inptext(name='ymin',value=self.kw['ymin'],size=12),
                               inptext(name='ymax',value=self.kw['ymax'],size=12)),
                    "",
                    "%s:%s" % (inptext(name='y2min',value=self.kw['y2min'],size=12),
                               inptext(name='y2max',value=self.kw['y2max'],size=12))
                    , spans=(1,2,1,2))
        #
        s = []
        for y in ('use_ylog','use_y2log'):
            t = []
            for i in ('Yes','No','Auto'):
                checked = (i == self.kw[y])
                t.append(self.radio(name=y, value=i, checked=checked, text=i))
            s.append(' '.join(t))
        self.addrow("Log Scale?",s[0],s[1],spans=(1,2,2))

        #
        self.addrow('','')
        self.addrow(self.button(text='Time From Present'),
                    self.select(id='time_ago',name='time_ago',
                                default=self.kw['time_ago'],
                                choices=self.ago_times), spans=(1,5))
        # 
        self.addrow('','')
        dval = [self.kw.get('date1',''),self.kw.get('date2','')]

        if dval[0] in (None,'None', ''): dval[0] = time_sec2str( time.time()-SEC_DAY)
        if dval[1] in (None,'None', ''): dval[1] = time_sec2str( time.time() )

        dates = ("%s <button id='date1_trig'>...</button>" % (inptext(size=22,name='date1',value=dval[0])),
                 "%s <button id='date2_trig'>...</button>" % (inptext(size=22,name='date2',value=dval[1])))

        self.addrow(self.button(text='Date Range'),"From: %s &nbsp;&nbsp; To: %s" % dates, spans=(1,5))
                                         
        self.addrow("<hr>", spans=(6,0))
        self.endtable()
        self.write(jscal_get_2dates)

        # main (lefthand side) of page done, 
       
        x = self.make_related_pvs_page(pv1,pvname2,submit=self.kw['submit'],
                                       time_ago=self.kw['time_ago'],
                                       date1=self.kw['date1'],
                                       date2=self.kw['date2'])

        self.draw_graph(pvname1=pv1,pvname2=pv2)

        self.write("</td><td>  %s </td></tr></table></form>" % x)

    def get_related_pvs(self,pvname):
        tmp = []  
        npv = normalize_pvname(pvname)
        r1 = self.arch.read_master("select * from pairs where pv1='%s' and score>1 order by score" %npv)
        for j in r1: tmp.append((j['score'],j['pv1'],j['pv2']))
        
        r2 = self.arch.read_master("select * from pairs where pv2='%s' and score>1 order by score" %npv)
        for j in r2: tmp.append((j['score'],j['pv1'],j['pv2']))

        tmp.sort()
        out = []
        for r in tmp:
            if   r[1] == npv and r[2] not in out:
                out.append(r[2])
            elif r[2] == npv and r[1] not in out:
                out.append(r[1])
        out.reverse()
        return out

    def __get_pvpairs(self,pv1,pv2):
        "fix and sort 2 pvs for use in the pairs tables"
        p = [normalize_pvname(pv1),normalize_pvname(pv2)]
        p.sort()
        return tuple(p)

    def increment_pair_score(self,pv1,pv2):
        # get current score:
        pvns = self.__get_pvpairs(pv1,pv2)
        where = "pv1='%s' and pv2='%s'" % pvns
        o  = self.arch.read_master("select * from pairs where %s" % where)
        try:
            score = int(o[0]['score'])
        except:
            score = -1

        if score < 1:
            q = "insert into pairs set score=%i, pv1='%s', pv2='%s'"
        else:
            q = "update pairs set score=%i where pv1='%s' and pv2='%s'"
            
        score = max(1, score+1)
        self.arch.read_master(q % (score,pvns[0],pvns[1]))

        
    def make_related_pvs_page(self,pvname,pvname2,submit='',time_ago='',date1='',date2=''):
        out = []
        r = self.get_related_pvs(pvname)

        args = ''
        if submit.startswith('Time From') and time_ago != '':
            args = '&time_ago=%s'  % (time_ago)
        elif submit.startswith('Date') and date1 != '' and date2 != '':
            args = '&date1=%s&date2=%s'  % (date1,date2)
            
        out.append("<p class='xtitle'>Related pvs:%s<p><font size=-1>" % '')  # pvname)
        if pvname2 != '':
            pvargs = 'pv2=%s&pv=%s' % (pvname,pvname2)            
            out.append("<a href='%s?%s%s'>Swap PV1 and 2</a></p><hr>" % (plotpage,pvargs,args))
        n = 0
        for pv2 in r:
            pvargs = 'pv=%s&pv2=%s' % (pvname,pv2)
            out.append("<a href='%s?%s%s'>%s</a></p>" % (plotpage,pvargs,args,pv2))
            n = n + 1
            if n>20: break
        out.append('</font>')
        return '\n'.join(out)
    

    def draw_graph(self,pvname1='',pvname2='',time_ago=None):

        # self.show_keys(title='AT Draw Graph')
        if DEBUG:
            self.write(" GRAPH %s / %s " % (pvname1,pvname2))
            self.write('<p> === Keys: === </p>')
            for key,val in self.kw.items():
                self.write(" %s :  %s <br>" % (key,val))
    
        t1 = time.time() + 10.0 # now+10seconds (make sure we don't lose "now")
        t0 = t1 - SEC_DAY

        action =  self.kw['submit']
        
        if action.startswith('Time From'):
            n,units = self.kw['time_ago'].split()
            if   units.startswith('mi'):   mult = 60.
            elif units.startswith('ho'):   mult = 3600.
            elif units.startswith('da'):   mult = SEC_DAY
            elif units.startswith('we'):   mult = SEC_DAY * 7
            elif units.startswith('mo'):   mult = SEC_DAY * 31.
            t0 = t1 - int(n) * mult
        else:
            dx = time.localtime()
            t0 = time_str2sec(self.kw['date1'])
            t1 = time_str2sec(self.kw['date2'])
            if t1 < t0:
                t1,t0 = t0,t1
                
        # self.write('<p> draw graph %i %i </p>' % (t0,t1))
        #
        froot  = "%s%s" % (config.webfile_prefix,timehash())

        f_png  = os.path.join(self.file_pref, "%s.png" % froot)
        l_png  = os.path.join(self.link_pref, "%s.png" % froot)

        f_gp   = os.path.join(self.file_pref, "%s.gp" % froot)
        l_gp   = os.path.join(self.link_pref, "%s.gp" % froot)

        f_dat  = os.path.join(self.file_pref, "%s.dat" % froot)
        f_dat2 = os.path.join(self.file_pref, "%s_2.dat" % froot)

        l_dat  = os.path.join(self.link_pref, "%s.dat" % froot)
        l_dat2 = os.path.join(self.link_pref, "%s_2.dat" % froot)


        self.gpfile = open(f_gp,'w')

        # get PV and related data
	epv1 = self.arch.get_pv(pvname1)
        pvinfo = self.arch.get_info(pvname1)
        pv2info = pvinfo
        ## self.write(" PV %s %s " % ( pvname1,epv1))

        if epv1 is None or pvinfo=={}: return ('','')
        if (epv1.pvname in (None,'')): return ('','')


        pvlabel = pvname1
        legend, tics = self.get_enum_legend(epv1)
        
        desc = pvinfo.get('description','')
        if desc in ('',None):
            desc = self.get_pvdesc(epv1)

        if desc != epv1.pvname:
            pvlabel = "%s (%s)" % (desc,epv1.pvname)

        file_link   = "<a href='%s'>data for %s</a>" % (l_dat,pvlabel)

        tlo, thi,npts,dat = self.save_data(epv1,t0,t1,f_dat,legend)
        if npts < 1:
            self.write("<br>Warning: No data for PV %s <br>" % (epv1))

        wait_for_pngfile = npts > 1       
        npts2 = 0
        n_dat = 1
        
        # start gnuplot session, set basic properties
        self.gp(self.gp_base)	 
	
        # are we plotting a second data set?
        if DEBUG:
             self.write("<br> pv2???  %s, %s <br>" % (pvname2, str(pvname2=='')))
            
        if pvname2 != '':
            epv2  = self.arch.get_pv(pvname2)
            epv2.connect()
            pv2info = self.arch.get_info(pvname2)

            self.increment_pair_score(pvname1,pvname2)
            if DEBUG:
                 self.write(" PV#2  !!! %s, %s" % (str(pvname2 is None), epv2.pvname))

                
            if epv2 is not None and epv2.pvname != '':
                val = epv2.get()
                leg2, tics2 = self.get_enum_legend(epv2)
                
                desc2 = pv2info.get('description','')
                if desc2 in ('',None):
                    desc2 = self.get_pvdesc(epv2)

                pv2label = pvname2
                if desc2 != pvname2:
                    pv2label = "%s (%s)" % (desc2, pvname2)

                file_link ="""<a href='%s'>data for %s</a><br>
                <a href='%s'>data for %s</a>""" % (l_dat,pvlabel,l_dat2,pv2label)

                tlo2, thi2, npts2,dat2 = self.save_data(epv2,t0,t1,f_dat2,leg2)
                if npts2 < 1:
                    self.write("<br>Warning: No data for PV %s <br>" % (pv2))
               
                tlo = min(tlo2, tlo)
                thi = max(thi2, thi)+1
                n_dat = 2
                self.gp(self.gp2_base)
                wait_for_pngfile = wait_for_pngfile and (npts2 > 1)

        if DEBUG:
            self.write(" # of data_sets %i" % n_dat)

        # now generate png plot
        self.gp("set output '%s'" % f_png)

        #         if npts > 1 or npts2>1:
        #             self.gp('set xrange ["%s":"%s"]' % (self.datestring(t0),self.datestring(t1)))
        #         else:
        self.gp('set xrange ["%s":"%s"]' % (self.datestring(t0),self.datestring(t1)))
            
        if pvinfo['type']=='double':
            ymin = str(pvinfo['graph_lo']) or ''
            if self.kw['ymin'] != '': ymin = self.kw['ymin']

            ymax = str(pvinfo['graph_hi']) or ''
            if self.kw['ymax'] != '': ymax = self.kw['ymax']

            self.gp("set yrange [%s:%s]" % (ymin,ymax))

            use_ylog = self.kw['use_ylog']
            if use_ylog == 'Auto' and pvinfo['type']=='double':
                if pvinfo['graph_type']=='log': use_ylog ='Yes'
            if use_ylog=='Yes':
                self.gp("set zero 1e-14")
                self.gp("set logscale y")
            
        if n_dat==2 and pv2info['type']=='double':

            y2min = str(pv2info['graph_lo']) or ''
            if self.kw['y2min'] != '': y2min = self.kw['y2min']

            y2max = str(pv2info['graph_hi']) or ''
            if self.kw['y2max'] != '': y2max = self.kw['y2max']

            self.gp("set y2range [%s:%s]" % (y2min,y2max))

            use_y2log = self.kw['use_y2log']
            if use_y2log == 'Auto' and pv2info['type']=='double':
                if pv2info['graph_type']=='log': use_y2log ='Yes'
            if use_y2log=='Yes':
                self.gp("set zero 1e-14")
                self.gp("set logscale y2")

        if epv1.type =='enum':
            self.gp("set ytics %s" % tics)
            try:
                n_enum = len(epv1.enum_strs)
            except:
                n_enum = 8
            self.gp("set yrange [-0.2:%f]" % (n_enum-0.8))
            
        if n_dat==2 and epv2.type =='enum':
            self.gp("set y2tics %s" % tics2)
            try:
                n_enum = len(epv2.enum_strs)
            except:
                n_enum = 8            
            self.gp("set y2range [-0.2:%f]" % (n_enum-0.8))
            
        if n_dat == 1:
            self.gp("set title  '%s'" % (desc))
            self.gp("set ylabel '%s'" % (pvlabel))
            self.gp("""plot '%s' u 1:4 w steps ls 1 t '%s', \\
            '%s' u 1:4 t '' w p 1 """ %  (f_dat,desc,f_dat))
        else:
            self.gp("set title '%s | %s'" % (desc,desc2))
            self.gp("set ylabel '%s'" % (pvlabel))
            self.gp("set y2label '%s'" % (pv2label))
            
            self.gp("""plot '%s' u 1:4 axis x1y1 w steps ls 1 t '%s',\\
            '%s' u 1:4 axis x1y1 t '' w p 1,\\
            '%s' u 1:4 axis x1y2 w steps ls 2 t '%s',\\
            '%s' u 1:4 axis x1y2 t '' w p 2 """ %
                    (f_dat,desc,f_dat,f_dat2,desc2,f_dat2))

        self.arch.use_currentDB()
        wait_count = 0
        png_size = 0
        while wait_for_pngfile:
            try:
                png_size   = os.stat(f_png)[6]
            except OSError:
               pass
            wait_for_pngfile = (png_size < 4) and (wait_count < 500)
            time.sleep(0.005)
            wait_count = wait_count + 1

        self.fix_gpfile(f_gp, self.file_pref)
        # self.write("<b> fix %s, %s / wait_count  = %i</b> " % (f_gp, self.file_pref,wait_count))

        if png_size > 0:
            self.write("<img src='%s'><br>" % l_png)
        else:
            self.write("<p>Cannot make requested graph!<p>")
            self.write("<br>Data for <b>%s</b>:<br>" % epv1.pvname)
            self.write("<table border=1 padding=1><tr><td>Date</td><td>Value</td></tr>")
            for d in dat:
                self.write("<tr><td>%s</td><td>%s</td></tr>" % (time.ctime(d[0]),d[1]))                
            self.write("</table>")
            if n_dat == 2:
                self.write("<p>Data for <b>%s</b>:<br>" % epv2.pvname)
                self.write("<table border=1 padding=1><tr><td>Date</td><td>Value</td></tr>")
                for d in dat2:
                    self.write("<tr><td>%s</td><td>%s</td></tr>" % (time.ctime(d[0]),d[1]))                
                self.write("</table>")


        self.write("<br>%s<br>" % (file_link))
        self.write("<a href='%s'>gnuplot script</a> <br>" % (l_gp))
        return


    def show_keys(self,**kw):
        for k,v in kw.items():
            self.write("%s : %s<br>" % (k,v))
            
    def get_pvdesc(self,pv):
        try:
            xpv = pv.pvname
            if xpv.endswith('.VAL'):  xpv = xpv[:-4]
            desc = epics.caget("%s.DESC" %  xpv)
        except:
            desc = None
        if desc in ('',None,' '):  desc = pv.pvname
        desc = desc.replace('"','_')
        desc = desc.replace("'",'_')
        return desc
    
    def get_enum_legend(self, pv):
        # self.write(" <BR> PV ENUM STR For %s<BR>" % repr(pv).replace('<','|') )
        legend, tics = '', ''
        if not pv.connected:
            pv.wait_for_connection(timeout=0.5)
        if pv.type == 'enum':
            xtmp = pv.get(as_string=True)        
            legend = " Legend: ["
            tics   = ''
            if pv.enum_strs is None:
                x = pv.get_ctrlvars()
            if pv.enum_strs is None:
                t0 = time.time()
                while pv.enum_strs is None and time.time()-t0 < 3.0:
                    x = pv.get(as_string=True)
                
            try:
                for i, nam in enumerate(pv.enum_strs):
                    legend = "%s %i= %s |" % (legend, i, nam)
                    tics   = '%s "%s" %i,' % (tics, nam, i)
                legend = "%s ]" % legend[:-1]
                tics   = "(%s)" % tics[:-1]
            except:
                legend = ''
                tics = ''
        return (legend,tics)

    def datestring(self,t):
        "return 'standard' date string given a unix timestamp"
        # Gnuplot hint: set xrange ["2005/08/17 09:00:00":"2005/08/17 14:00:00"]
        return time.strftime("%Y%m%d %H%M%S", time.localtime(t))

    def save_data(self,pv,t0,t1,fout,legend):
        "get data from database, save into tmp gnuplot-friendly file"
        dat,stat = self.arch.get_data(pv.pvname,t0,t1)

        pvname = pv.pvname
        if DEBUG:
            self.write("<p>DATA for PV %s (%i:%i) #points =%i<br>\n" % (pvname,t0,t1,len(dat)))
            for i in stat:
                self.write("%s<br>\n" % str(i))

        npts = len(dat)
        errstring = ''
        try:
            tlo = dat[0][0]
            thi = dat[npts-1][0]
        except IndexError:
            dat = [(t0,None),(t1,None)]
            npts,tlo,thi = 0,t0,t1
            errstring = 'No data for %s' % pv.pvname
            
        #  now write data to gnuplot-friendly file
        dstr = self.datestring
        f = open(fout, 'w')
        f.write("# %s (%s)\n" % (pv.pvname,pv.type))
        f.write("# requested time_span:  [%s , %s] \n" % (dstr(t0),dstr(t1)))
        f.write("# actual    time_span:  [%s , %s] \n" % (dstr(tlo),dstr(thi)))
        if legend != '':
            f.write("# %s \n" % legend)
        if errstring != '':
            f.write("# ERROR: %s \n" % legend)
        else:
            f.write("# n_points: %i \n" % npts)
        f.write("#-------------------------------\n")
        f.write("#  date      time          value\n")
        for j in dat:
            val  = j[1]
            if isinstance(val, str):
                try:
                    val = float(val)
                except:
                    pass
        
            f.write("%s %.3f %s\n" % (dstr(j[0]), j[0], j[1]))
        f.close()
        return (tlo, thi, npts,dat)
    
    def argclean(self,argval,formval):
        v = formval.strip()
        if v != '': return v

        a = argval
        if a is None: a = ''
        if not isinstance(a,str): a = str(a)
        return a.strip()
        
    def OLD_show_plot(self,pv=None,pv2=None,time_ago=None,date1=None,date2=None,**kw):
        self.kw.update(kw)
        pv1 = self.argclean(pv,  self.kw['text_pv'])
        pv2 = self.argclean(pv2, self.kw['text_pv2'])        

        self.arch.db.get_cursor()

        if pv1 != '':
            pv1 = normalize_pvname(pv1)
            self.html_title = "%s for %s" % (self.html_title,pv1)
            if not self.in_database(pv1):  self.arch.add_pv(pv1)
            
        if pv2 != '':
            pv2 = normalize_pvname(pv2)
            self.html_title = "%s and %s" % (self.html_title,pv2)
            if not self.in_database(pv2):  self.arch.add_pv(pv2)            
# 
        self.starthtml()
        self.show_links(pv=pv1,help='plotting',active_tab='')
        self.draw_form(pv1=pv1,pv2=pv2,time_ago=time_ago,date1=None,date2=None)
        self.endhtml()

        self.arch.db.put_cursor()

        return self.get_buffer()


    def update_kw(self,key,arg=None):
        if key is None: return arg
        if key not in  self.kw: self.kw[key] = ''
        if arg is None: arg = ''
        if not isinstance(arg,str): arg = str(arg)
        if arg != '': self.kw[key] = arg.strip()
        return arg.strip()

    def do_plot(self,pv='',pv2='',time_ago=None,date1=None,date2=None,**kw):
        self.kw.update(kw)
        self.update_kw('pv',pv)
        self.update_kw('pv2',pv2)
        self.update_kw('time_ago',time_ago)
        self.update_kw('date1',date1)
        self.update_kw('date2',date2)
        
        self.starthtml()

        if self.kw.get('text_pv','') not in ('',None):
            self.kw['pv'] = self.kw['text_pv']

        if self.kw.get('text_pv2','') not in ('',None):
            self.kw['pv2'] = self.kw['text_pv2']
        
        pv1 = self.kw.get('pv','')
        pv2 = self.kw.get('pv2','')

        action =  self.kw.get('submit','')
        if action == '':
            action = 'Time From Present'
            if (self.kw.get('date1','') != '' and
                self.kw.get('date2','') != ''):
                action = 'Date Range'
                
        if self.kw.get('submit','') == '':
            self.kw['submit'] = action

        self.arch.db.get_cursor()
        warnings = []
        if pv1 != '':
            pv1 = normalize_pvname(pv1)
            self.html_title = "%s for %s" % (self.html_title,pv1)
            if not self.in_database(pv1):
                add_ok = self.arch.add_pv(pv1)
                if add_ok is None:
                    warnings.append(" Warning: cannot add PV '%s'<br>" % pv1 )
                    
        if pv2 != '':
            pv2 = normalize_pvname(pv2)
            self.html_title = "%s and %s" % (self.html_title,pv2)
            if not self.in_database(pv2):
                add_ok = self.arch.add_pv(pv2)            
                if add_ok is None:
                    warnings.append(" Warning: cannot add PV '%s'<br>" % pv2 )

        self.show_links(pv=pv1,help='plotting',active_tab='')
        
        for w in warnings: self.write(w)
        
        # self.show_keys(title='AT DO PLOT')

        self.draw_form(pv1=pv1,pv2=pv2,time_ago=time_ago,date1=date1,date2=date2)
        self.endhtml()

        self.arch.db.put_cursor()

        return self.get_buffer()

    def show_keys(self,title=''):
        self.write('===== %s Keys: === </p>' % title)
        for key,val in self.kw.items():
            self.write(" %s :  '%s' <br>" % (key,val))
        self.write('=====')
