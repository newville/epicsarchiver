#!/usr/bin/python
import os
import time
import EpicsCA

from EpicsArchiver import ArchiveMaster, Archiver, config, add_pv_to_cache
from EpicsArchiver.util import SEC_DAY, clean_string, clean_input, normalize_pvname, timehash, \
     increment_pair_score, tformat

from HTMLWriter import HTMLWriter, jscal_get_2dates

DEBUG=True
DEBUG=False
cgiroot   = config.cgi_url


thispage   = "%s/viewer.py" % cgiroot
adminpage  = "%s/admin.py" % cgiroot
pvinfopage = "%s/admin.py/pvinfo"       % cgiroot
relpv_page = "%s/admin.py/related_pvs"  % cgiroot
instspage  = "%s/instruments.py"  % cgiroot
statuspage = "%s/status.py" % cgiroot

os.environ['GNUTERM'] = 'png'

import Gnuplot
Gnuplot.GnuplotOpts.default_term='png'

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
set yrange [:]
set y2range [:]
set y2tics
set ytics nomirror
"""
    html_title = "Epics Archiver Data Viewer"
        
    def __init__(self, arch=None, cache=None, **kw):
        HTMLWriter.__init__(self)

        self.arch   = arch or Archiver()
        self.master = self.arch.master
        
        self._gp = Gnuplot.Gnuplot() # "%s/out.gp" % self.file_pref)
        self.kw  = {'form_pv':'', 'form_pv2':'',  'use_ylog':'', 'use_y2log': '',
                    'submit': 'Time From Present', 'time_ago': '1 day', 
                    'ymin':'', 'ymax':'', 'y2min':'', 'y2max':'',
                    'date1': '', 'date2': ''}
        self.kw.update(kw)
        if not self.file_pref.endswith('/'): self.file_pref = "%s/" % self.file_pref

    def gp(self,s):
        " simple wrapper around gnuplot "
        self.gpfile.write("%s\n" % s)
        self._gp(s)

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
    

    def draw_form(self,arg_pv1=None,arg_pv2=None,**kw):

        action = self.kw.get('submit','Time From')
        if action.startswith('Swap') and arg_pv2 not in (None,''):
            arg_pv1,arg_pv2 = arg_pv2,arg_pv1

        pvname1 = arg_pv1 or ''
        pvname2 = arg_pv2 or ''
        self.write("""<table><tr><td><form action ="%s" enctype="multipart/form-data"  method ="POST">
        <p>""" % (thispage))


        tx = "Epics PV Archive: %s" % (time.ctime())

        self.write("<table border=0 cellpadding=1>")
        #
        self.write("<tr><td colspan=5>")
        pv1 = self.argclean(pvname1,  self.kw['form_pv'])
       
        self.show_links(pv=pv1)
        self.write("</td></tr>")
        self.write("<tr><td colspan=5 class='xtitle'>&nbsp;&nbsp;&nbsp;&nbsp; %s</td></tr>" % tx)
        #
        many_spaces= "<tr class='xx'><td colspan=5> %s</td></tr> " % ('&nbsp;'*5)
        self.write(many_spaces)


        self.write("""<tr><td>PV 1:</td>
        <td><input type="text" name="form_pv"  value="%s" size=30></td>
        <td></td><td>PV 2:</td>
        <td><input type="text" name="form_pv2" value="%s" size=30></td>
        </tr>""" % (pvname1,pvname2))
        #
        self.write("""<tr><td>PV (Y) range:</td>  <td>
        <input type="text" name="ymin"  value="%(ymin)s"  size=12> :
        <input type="text" name="ymax"  value="%(ymax)s"  size=12> </td><td colspan=2></td> <td>
        <input type="text" name="y2min" value="%(y2min)s" size=12> :
        <input type="text" name="y2max" value="%(y2max)s" size=12> </td>
        </tr>"""   % (self.kw))
            
        #
        self.write("<tr><td>Log Scale?</td><td>")
        if self.kw['use_ylog'] == '': self.kw['use_ylog'] = 'Auto'
        for i in ('Yes','No','Auto'):
            sel = ''
            if i == self.kw['use_ylog']:
                sel = "checked=\"true\""
            self.write('<input type="radio" %s name="use_ylog" value="%s">&nbsp;%s' % (sel,i,i))
        self.write("</td><td></td><td></td><td>")

        if self.kw['use_y2log'] == '': self.kw['use_y2log'] = 'Auto'
        for i in ('Yes','No','Auto'):
            sel = ''
            if i == self.kw['use_y2log']:
                sel = "checked=\"true\""
            self.write('<input type="radio" %s name="use_y2log" value="%s">&nbsp;%s' % (sel,i,i))
        self.write("</td></tr>")

        #
        self.write(many_spaces)
        self.write("<tr><td><input type='submit' name='submit'  value='Time From Present'></td><td colspan=2>")
        self.write("<select id='time_ago' name='time_ago'>")
        for i in self.ago_times:
            extra = ' '
            if i == self.kw['time_ago']: extra = 'selected'
            self.write("<option %s value='%s'>%s" % (extra, i, i))
        self.write( "</select>" )
        self.write("</td><td></td><td>")
        self.write("</td></tr>")
        # 
        self.write(many_spaces)
        self.write("<tr><td><input type='submit' name='submit'  value='Date Range'></td>")

        d1val = self.kw.get('date1','')
        d2val = self.kw.get('date2','')
        if d1val in (None,'None', ''): d1val = self.time_sec2str( time.time()-SEC_DAY)
        if d2val in (None,'None', ''): d2val = self.time_sec2str( time.time() )


        self.write("<td colspan=2> From:")
        dform = "<input type='text' width=22 id='%(d)s' name='%(d)s' value='%(v)s'/><button id='%(d)s_trig'>...</button>"
        self.write(dform % ({'d':'date1','v':d1val}))
        self.write("</td><td colspan=2> &nbsp;&nbsp; To:")
        self.write(dform % ({'d':'date2','v':d2val}))


        self.write("</td></tr><tr><td></td></tr><tr><td colspan=5><hr></td></tr></table>")
        self.write(jscal_get_2dates)

        # main (lefthand side) of page done, 
       
        x = self.make_related_pvs_page(arg_pv1,pvname2)

        self.draw_graph(arg_pv1,arg_pv2)

        self.write("</td><td>  %s </td></tr></table></form>" % x)

    def make_related_pvs_page(self,pvname,pvname2):
        out = []
        r = self.master.get_related_pvs(pvname)
        if pvname2 != '': out.append("<input type='submit' name='submit' value='Swap PV 1 and 2'><p>")        
        out.append("<p class='xtitle'>related pvs:%s<p>" % '')  # pvname)
        n = 0
        for pv2 in r:
            out.append("<font size=-2><a href='%s?pv=%s&pv2=%s'>%s</a></font></p>" % (thispage,pvname,pv2,pv2))
            n = n + 1
            if n>20: break
        return '\n'.join(out)
    
    def time_sec2str(self,sec=None):
        return tformat(t=sec,format="%Y-%m-%d %H:%M:%S")
        
    def time_str2sec(self,str):
        xdat,xtim=str.split(' ')
        hr,min = xtim.split(':')
        yr,mon,day = xdat.split('-')
        dx = time.localtime()
        return time.mktime((int(yr),int(mon),int(day),int(hr),int(min), 0,0,0,dx[8]))

    def draw_graph(self,arg_pv1=None,arg_pv2=None):
        if DEBUG:
            self.write(" GRAPH %s / %s " % (arg_pv1,arg_pv2))
            self.write('<p> === Keys: === </p>')
            for key,val in self.kw.items():
                self.write(" %s :  %s <br>" % (key,val))
    
        t1 = time.time()
        t0 = t1 - SEC_DAY
        action =  self.kw.get('submit','Time From')
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
            t0 = self.time_str2sec(self.kw['date1'])
            t1 = self.time_str2sec(self.kw['date2'])
            if t1 < t0:
                t1,t0 = t0,t1
                
        # self.write('<p> draw graph %i %i </p>' % (t0,t1))
        #
        froot  = "pv%s" % timehash()

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

        pv = self.arch.get_pv(arg_pv1)
        pv.connect()
        pvinfo = self.arch.get_info(arg_pv1)
        pv2info = pvinfo
        ## self.write(" PV %s %s " % ( arg_pv1,pv))

        if pv is None or pvinfo=={}: return ('','')
        if (pv.pvname in (None,'')): return ('','')
        desc = self.get_pvdesc(pv)
        pvlabel = pv.pvname
        if desc!=pv.pvname: pvlabel = "%s (%s)" % (pv.pvname,desc)
        legend,tics = self.get_enum_legend(pv)        
        file_link   = "<a href='%s'>data for %s</a>" % (l_dat,pvlabel)

        tlo, thi,npts = self.save_data(pv,t0,t1,f_dat,legend)
        npts2 = 0
        n_dat = 1
        
        # start gnuplot session, set basic properties
        self.gp(self.gp_base)

        # are we plotting a second data set?
        if DEBUG:
            self.write("<br> arg_pv2???  %s, %s <br>" % (arg_pv2, str(arg_pv2=='')))
            
        if arg_pv2 != '':
            pv2  = self.arch.get_pv(arg_pv2)
            pv2.connect()
            pv2info = self.arch.get_info(arg_pv2)
            self.master.increment_pair_score(arg_pv1,arg_pv2)
            if DEBUG:
                self.write(" PV#2  !!! %s, %s" % (str(pv2 is None), pv2.pvname))
                
            if (pv2 is not None) and (pv2.pvname != ''):
                val = pv2.get()
                desc2 = self.get_pvdesc(pv2)
                pv2label = pv2.pvname
                if desc2!=arg_pv2:  pv2label = "%s (%s)" % (pv2.pvname,desc2)

                file_link ="""<a href='%s'>data for %s</a><br>
                <a href='%s'>data for %s</a>""" % (l_dat,pvlabel,l_dat2,pv2label)

                leg2,tics2 = self.get_enum_legend(pv2)
                tlo2, thi2, npts2 = self.save_data(pv2,t0,t1,f_dat2,leg2)
                tlo = min(tlo2, tlo)
                thi = max(thi2, thi)
                n_dat = 2
                self.gp(self.gp2_base)

        if DEBUG:
            self.write(" # of data_sets %i" % n_dat)

        # now generate png plot
        self.gp("set output '%s'" % f_png)

        if npts > 1 or npts2>1:
            self.gp('set xrange ["%s":"%s"]' % (self.datestring(t0),self.datestring(t1)))
        else:
            self.gp('set xrange ["%s":"%s"]' % (self.datestring(tlo),self.datestring(thi)))

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

        if pv.type =='enum':
            self.gp("set ytics %s" % tics)
            try:
                n_enum = len(pv.enum_strings)
            except:
                n_enum = 8
            self.gp("set yrange [-0.2:%f]" % (n_enum-0.8))
            
        if n_dat==2 and pv2.type =='enum':
            self.gp("set y2tics %s" % tics2)
            try:
                n_enum = len(pv2.enum_strings)
            except:
                n_enum = 8            
            self.gp("set y2range [-0.2:%f]" % (n_enum-0.8))
            
        if n_dat == 1:
            self.gp("set title  '%s'" % (pvlabel))
            self.gp("set ylabel '%s'" % (pvlabel))
            self.gp("""plot '%s' u 1:4 w steps ls 1 t '%s', \\
            '%s' u 1:4 t '' w p 1 """ %  (f_dat,pvlabel,f_dat))
        else:
            self.gp("set title '%s | %s'" % (pvlabel,pv2label))
            self.gp("set ylabel '%s'" % (pvlabel))
            self.gp("set y2label '%s'" % (pv2label))
            
            self.gp("set y2range [:]")
            self.gp("set ytics nomirror")
            self.gp("set y2tics")

            self.gp("""plot '%s' u 1:4 axis x1y1 w steps ls 1 t '%s',\\
            '%s' u 1:4 axis x1y1 t '' w p 1,\\
            '%s' u 1:4 axis x1y2 w steps ls 2 t '%s',\\
            '%s' u 1:4 axis x1y2 t '' w p 2 """ %
                    (f_dat,pvlabel,f_dat,f_dat2,pv2label,f_dat2))

        self.arch.use_currentDB()
        wait_for_pngfile = True
        wait_count = 0
        while wait_for_pngfile:
            try:
                png_size   = os.stat(f_png)[6]
            except OSError:
                png_size = 0
                
            wait_for_pngfile = (png_size < 4) and (wait_count < 1000)
            time.sleep(0.005)
            wait_count = wait_count + 1

        self.fix_gpfile(f_gp, self.file_pref)
        # self.write("<b> fix %s, %s </b> " % (f_gp, self.file_pref))

        if png_size > 0:
            self.write("<img src='%s'><br>" % l_png)
        else:
            self.write("<b>cannot make graph (String Data?)</b><br>")            
        self.write("<br>%s<br>" % (file_link) )
        
        self.write("<a href='%s'>gnuplot script</a> <br>" % (l_gp))
        return

    def show_keys(self,**kw):
        for k,v in kw.items():
            self.write("%s : %s<br>" % (k,v))
            
    def get_pvdesc(self,pv):
        try:
            xpv = pv.pvname
            if xpv.endswith('.VAL'):  xpv = xpv[:-4]
            desc = EpicsCA.caget("%s.DESC" %  xpv)
        except:
            desc = None
        if desc in ('',None,' '):  desc = pv.pvname
        desc = desc.replace('"','_')
        desc = desc.replace("'",'_')
        return desc
    
    def get_enum_legend(self,pv):
        legend = ''
        tics   = ''
        if pv.type == 'enum':
            xtmp = pv.get()        
            legend = " Legend: ["
            tics   = ''
            enumstrings = pv.enum_strings
            try:
                for i in range(len(enumstrings)):
                    legend = "%s %i= %s |" % (legend,i, enumstrings[i])
                    tics   = '%s "%s" %i,' % (tics, enumstrings[i],i)
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
            self.write("<p>DATA for PV %s %i  %i #points =%i<br>\n" % (pvname,t0,t1,len(dat)))
            for i in stat:
                self.write("%s<br>\n" % str(i))

        npts = len(dat)
        tlo = dat[0][0]
        thi = dat[npts-1][0]
        #  now write data to gnuplot-friendly file
        dstr = self.datestring
        f = open(fout, 'w')
        f.write("# %s (%s)\n" % (pv.pvname,pv.type))
        f.write("# requested time_span:  [%s , %s] \n" % (dstr(t0),dstr(t1)))
        f.write("# actual    time_span:  [%s , %s] \n" % (dstr(tlo),dstr(thi)))
        if legend != '':
            f.write("# %s \n" % legend)
        f.write("# n_points: %i \n" % npts)
        f.write("#-------------------------------\n")
        f.write("#  date      time          value\n")
        for j in dat:
            f.write("%s %i %s\n" % (dstr(j[0]), j[0], j[1]))
        f.close()
        return (tlo, thi, npts)
    
    def argclean(self,argval,formval):
        v = formval.strip()
        if v != '': return v

        a = argval
        if a is None: a = ''
        if not isinstance(a,str): a = str(a)
        return a.strip()
        
    def show_pv(self,pv=None,pv2=None):
        arg_pv1 = self.argclean(pv,  self.kw['form_pv'])
        arg_pv2 = self.argclean(pv2, self.kw['form_pv2'])        

        # if DEBUG:
        #    self.write('<br>:: show_pv  // %s // %s //<br>' % ( arg_pv1, arg_pv2))
            
        if arg_pv1 != '':
            arg_pv1 = normalize_pvname(arg_pv1)
            self.html_title = "%s for %s" % (self.html_title,arg_pv1)
            if not self.in_database(arg_pv1):  self.arch.add_pv(arg_pv1)
            
        if arg_pv2 != '':
            arg_pv2 = normalize_pvname(arg_pv2)
            self.html_title = "%s and %s" % (self.html_title,arg_pv2)
            if not self.in_database(arg_pv2):  self.arch.add_pv(arg_pv2)            
# 
        self.starthtml()
        self.draw_form(arg_pv1,arg_pv2)
        
        self.endhtml()
        return self.get_buffer()

