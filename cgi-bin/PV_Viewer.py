#!/usr/bin/python
import os
import time
import pvarch
import pvcache
import EpicsCA

DEBUG=False
cgiroot   = "http://cars9.uchicago.edu/cgi-bin/gse_status"

if DEBUG:
    cgiroot =  "http://cars9.uchicago.edu/~newville/py"

thispage  = "%s/archiver.py" % cgiroot
adminpage = "%s/admin.py" % cgiroot
pvinfopage= "%s/admin.py/show_pvinfo" % cgiroot
statuspage= "%s/status.py" % cgiroot

os.environ['GNUTERM'] = 'png'

import Gnuplot
Gnuplot.GnuplotOpts.default_term='png'

ISEC_DAY = 86400  # sec / day
REFRESH_TIME = "%i" % (ISEC_DAY * 7)

def random_string(n):
    """generate a string of length n of random numbers+letters """
    s = ['a']*n
    from random import seed, randrange
    from string import printable
    seed(time.time())
    s[0] = printable[randrange(10,36)] # first char is alpha
    for i in range(1,n):               # rest are alphanumeric
        s[i] = printable[randrange(0,36)]
    return ''.join(s)

class HTMLWriter:
    style = """pre {text-indent: 30px}
h4 {font:bold 18px verdana,arial,sans-serif;color:#044484;font-weight:bold;font-style:italic;}
.xtitle {font-family: verdana, arial, san-serif; font-size: 13pt;
         font-weight:bold; font-style:italic;color:#900000}
.xx {font-size: 3pt;}
body {margin:10px; padding:0px;background:#FDFDFD; font:bold 14px verdana, arial, sans-serif;}
#content {text-align:justify;  background:#FDFDFD; padding: 0px;border:4px solid #88000;
border-top: none;  z-index: 2; }
#tabmenu {font: bold 11px verdana, arial, sans-serif;
border-bottom: 2px solid #880000; margin: 1px; padding: 0px 0px 4px 0px; padding-left: 20px;}
#tabmenu li {display: inline;overflow: hidden;margin: 1px;list-style-type: none; }
#tabmenu a, a.active {color: #4444AA;background: #EEDD88;border: 2px solid #880000;
padding: 3px 3px 4px 3px;margin: 0px ;text-decoration: none; }
#tabmenu a.active {color: #CC0000;background: #FCFCEA;border-bottom: 2px solid #FCFCEA;}
#tabmenu a:hover {color: #CC0000; background: #F9F9E0;}
"""
    js_setup = '''<link rel="stylesheet" type="text/css" media="all"
    href="http://cars9.uchicago.edu/cgi-data/jscal/calendar-system.css" />
<script type="text/javascript" src="../../cgi-data/jscal/calendar.js"></script>
<script type="text/javascript" src="../../cgi-data/jscal/lang/calendar-en.js"></script>
<script type="text/javascript" src="../../cgi-data/jscal/calendar-setup.js"></script>
'''
    js_cal = """<script type='text/javascript'>
    function setdate2(cal) {
        var date  = cal.date;
        var time  = date.getTime()
        var f1    = document.getElementById("date1");
        var f2    = document.getElementById("date2");
        var tago  = document.getElementById("time_ago");
        var tarr  = new Array();
        tarr      = tago.value.split(' ');
        if (f1 == cal.params.inputField) {
            var tunit = Date.DAY;
            var tstr = tarr[1].substring(0,2);
            if      (tstr == 'ho'){ tunit= Date.HOUR;   }
            else if (tstr == 'we'){ tunit= Date.WEEK;   }
            else if (tstr == 'mo'){ tunit= Date.DAY*31; }
            time     += tarr[0] * tunit; 
            var date2 = new Date(time);
            f2.value  = date2.print("%Y-%m-%d %H:%M");
          }
     }
     Calendar.setup({inputField : "date1",
             ifFormat   : "%Y-%m-%d %H:%M",
             showsTime  : true,
             timeFormat : 24,
             singleClick: false,
             button     : "date1_trig",
             weekNumbers: false,
             onUpdate   : setdate2  });
     Calendar.setup({inputField : "date2",
             ifFormat   : "%Y-%m-%d %H:%M",
             showsTime  : true,
             timeFormat : 24,
             singleClick: false,
             button     : "date2_trig",
             weekNumbers: false,
             });</script>"""
    
    links= (("http://cars9.uchicago.edu/gsecars/webcam/", "GSECARS Web Cameras"),
            ("http://www.aps.anl.gov/asd/operations/gifplots/statgif.html","APS Status"),
            (statuspage, "Beamline Status"),
            (adminpage,"Archiver Admin Page")   )

    def __init__(self, **args):
        self.tabledef  ="<table width=90% cellpadding=0 cellspacing=1>"
        self.buffer  = []

    def write(self,s):
        self.buffer.append(s)
        # = "%s%s\n" % (self.buffer,s)

    def get_buffer(self):
        r = '\n'.join(self.buffer)
        self.buffer =[]
        return r

    def end_table(self):
        self.write("</table><br>")

    def starthtml(self,refresh=''):
        if self.html_title in (None,'',' '):  self.html_title = ' '
        if refresh == '' : refresh = REFRESH_TIME
        self.write("<html><head><title>%s</title>" % self.html_title)
        self.write('<meta http-equiv="Pragma"  content="no-cache">')
        self.write('<meta http-equiv="Refresh" content="%s">' % refresh)
        self.write('<style type="text/css">%s</style>' %  self.style)
        ##
        self.write(self.js_setup)
        self.write("</head><body>")

    def show_links(self):
        self.write("<ul id='tabmenu'>")
        for url,name in self.links:
            self.write("<li><a  href='%s'>%s</a></li>" % (url,name))
        self.write("</ul><br>")

    def endhtml(self):
        s = "["
        for url,name in self.links:
            s = "%s<a href='%s'>%s</a> |" % (s,url,name)
        s = s[:-1] + ']'
        self.write("</body></html>")

class PV_Viewer(HTMLWriter):
    ago_times = ('1 hour', '2 hours', '3 hours', '6 hours','8 hours','12 hours', 
                 '1 day','2 days','3 days', '1 week', '2 weeks', '1 month')

    # available years: 2001 to current
    years   = range(2001, time.localtime()[0]+1)
    months  = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    days    = (31,28,31,30,31,30,31,31,30,31,30,31)
    minutes = ('00','05','10','15','20','25', '30','35','40','45','50','55')
    file_pref  = "/www/apache/htdocs/cgi-data/pvarch/"
    link_pref  = "http://cars9.uchicago.edu/cgi-data/pvarch/"

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
    def __init__(self,**kw):
        HTMLWriter.__init__(self)
        self.arch  = pvarch.Archiver()
        self.cache = pvcache.PVCache()
        self._gp = Gnuplot.Gnuplot() # "%s/out.gp" % self.file_pref)
        self.kw  = {'form_pv':'', 'form_pv2':'',  'use_ylog':'', 'use_y2log': '',
                    'submit': 'Time From Present', 'time_ago': '1 day', 
                    'ymin':'', 'ymax':'', 'y2min':'', 'y2max':'',
                    'date1': '', 'date2': ''}
        self.kw.update(kw)

    def gp(self,s):
        " simple wrapper around gnuplot "
        self.gpfile.write("%s\n" % s)
        self._gp(s)
        
    def in_database(self,pvname):
        if not pvname: return False
        if pvname == '': return False
        x = pvname
        if x.find('.') == -1: x = "%s.VAL" % x
        return x in self.arch.get_pvlist()
    

    def draw_form(self,arg_pv1=None,arg_pv2=None,**kw):

        action = self.kw.get('submit','Time From')
        if action.startswith('Swap') and arg_pv2 not in (None,''):
            arg_pv1,arg_pv2 = arg_pv2,arg_pv1

        pvname1 = arg_pv1 or ''
        pvname2 = arg_pv2 or ''
        self.write("""<table><tr><td><form action ="%s" enctype="multipart/form-data"  method ="POST">
        <p>""" % (thispage))


        tx = "GSECARS PV Database: %s" % (time.ctime())

        self.write("<table border=0 cellpadding=1>")
        #
        self.write("<tr><td colspan=5>")
        self.show_links()
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
        if d1val in (None,'None', ''): d1val = self.time_sec2str( time.time()-ISEC_DAY)
        if d2val in (None,'None', ''): d2val = self.time_sec2str( time.time() )


        self.write("<td colspan=2> From:")
        dform = "<input type='text' width=22 id='%(d)s' name='%(d)s' value='%(v)s'/><button id='%(d)s_trig'>...</button>"
        self.write(dform % ({'d':'date1','v':d1val}))
        self.write("</td><td colspan=2> &nbsp;&nbsp; To:")
        self.write(dform % ({'d':'date2','v':d2val}))

        # self.write("<input type='text' width=22 id='date2' name='date2' value='%s'/><button id='date2_trig'>...</button>" % d2val)

        self.write("</td></tr><tr><td></td></tr><tr><td colspan=5><hr></td></tr></table>")
        self.write(self.js_cal)

        # main (lefthand side) of page done, 
       

        x = self.make_related_pvs_page(arg_pv1,pvname2)

        self.draw_graph(arg_pv1,arg_pv2)

        self.write("</td><td>  %s </td></tr></table></form>" % x)

    def make_related_pvs_page(self,pvname,pvname2):
        out = []
        r = self.arch.get_related_pvs(pvname)
        if pvname2 != '': out.append("<input type='submit' name='submit' value='Swap PV 1 and 2'><p>")        
        out.append("<p class='xtitle'>related pvs:%s<p>" % '')  # pvname)
        n = 0
        for pv2 in r:
            out.append("<font size=-2><a href='%s?pv=%s&pv2=%s'>%s</a></font></p>" % (thispage,pvname,pv2,pv2))
            n = n + 1
            if n>20: break
        return '\n'.join(out)
    
    def time_sec2str(self,sec=None):
        if sec is None: sec = time.time()
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(sec))
        
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
                self.write("<p>  %s :  %s </p>" % (key,val))
    
        t1 = time.time()
        t0 = t1 - ISEC_DAY
        action =  self.kw.get('submit','Time From')
        if action.startswith('Time From'):
            n,units = self.kw['time_ago'].split()
            if   units.startswith('ho'):   mult = 3600.
            elif units.startswith('da'):   mult = ISEC_DAY
            elif units.startswith('we'):   mult = ISEC_DAY * 7
            elif units.startswith('mo'):   mult = ISEC_DAY * 31.
            t0 = t1 - int(n) * mult
        else:
            dx = time.localtime()
            t0 = self.time_str2sec(self.kw['date1'])
            t1 = self.time_str2sec(self.kw['date2'])
            if t1 < t0:
                t1,t0 = t0,t1
                
        # self.write('<p> draw graph %i %i </p>' % (t0,t1))
        #
        froot  = "pv%s"      % random_string(8)
        f_png  = "%s%sa.png" % (self.file_pref,froot)
        f_dat  = "%s%sa.dat" % (self.file_pref,froot)
        f_gp   = "%s%sa.gp"  % (self.file_pref,froot)
        f2_dat = "%s%sb.dat" % (self.file_pref,froot)


        self.gpfile = open(f_gp,'w')
        png_link= "%s%sa.png" % (self.link_pref,froot)

        # get PV and related data

        pv = self.arch.get_pv(arg_pv1)

        ## self.write(" PV %s %s " % ( arg_pv1,pv))

        if pv is None: return ('','')
        if (pv.pvname in (None,'')): return ('','')
        desc = self.get_pvdesc(pv)
        pvlabel = pv.pvname
        if desc!=pv.pvname: pvlabel = "%s (%s)" % (pv.pvname,desc)
        legend,tics = self.get_enum_legend(pv)        
        file_link   = """<a href='%s%sa.dat'>data for %s</a>
        """ % (self.link_pref,froot,pvlabel)

        # get data, write data
        ## self.write("<p>====  SAVING %s %s %s" % (pv.pvname,f_dat,legend))

        self.save_data(pv,t0,t1,f_dat,legend)
        n_dat = 1

        # start gnuplot session, set basic properties
        self.gp(self.gp_base)

        # are we plotting a second data set?
        if arg_pv2 != '':
            pv2  = self.arch.get_pv(arg_pv2)
            self.arch.increment_pair_score(arg_pv1,arg_pv2)
            if pv2 and pv2.pvname not in (None,''):
                val = pv2.get()
                desc2 = self.get_pvdesc(pv2)
                pv2label = pv2.pvname
                if desc2!=arg_pv2:  pv2label = "%s (%s)" % (pv2.pvname,desc2)

                file_link ="""<a href='%s%sa.dat'>data for %s</a><br>
                <a href='%s%sb.dat'>data for %s</a>
                """ % (self.link_pref,froot,pvlabel,self.link_pref,froot,pv2label)

                leg2,tics2 = self.get_enum_legend(pv2)
                self.save_data(pv2,t0,t1,f2_dat,leg2)            
                n_dat = 2
                self.gp(self.gp2_base)

        # now generate png plot
        self.gp("set output '%s'" % f_png)

        self.gp('set xrange ["%s":"%s"]' % (self.datestring(t0),self.datestring(t1)))

        if pv.type=='double':
            if (self.kw['ymin']!='' or self.kw['ymax']!=''):
                self.gp("set yrange [%(ymin)s:%(ymax)s]" % self.kw)
            else:
                self.gp("set yrange [:]")
            use_ylog = self.kw['use_ylog']
            if use_ylog == 'Auto' and pv.type=='double':
                if pv.graph_type=='LOG': use_ylog ='Yes'
            if use_ylog=='Yes':  self.gp("set logscale y")
            
        if n_dat==2 and pv2.type=='double':
            if (self.kw['y2min']!='' or self.kw['y2max']!=''):
                self.gp("set y2range [%(y2min)s:%(y2max)s]" % self.kw)

            use_y2log = self.kw['use_y2log']
            if use_y2log == 'Auto' and pv2.type=='double':
                if pv2.graph_type=='LOG': use_y2log ='Yes'
            if use_y2log=='Yes':  self.gp("set logscale y2")

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
            self.gp("""plot '%s' u 1:4 w steps ls 1 t '%s', \
            '%s' u 1:4 t '' w p 1 """ %
                    (f_dat,pvlabel,f_dat))
        else:
            self.gp("set title '%s | %s'" % (pvlabel,pv2label))
            self.gp("set ylabel '%s'" % (pvlabel))
            self.gp("set y2label '%s'" % (pv2label))
            
            self.gp("set y2range [:]")
            self.gp("set ytics nomirror")
            self.gp("set y2tics")

            self.gp("""plot '%s' u 1:4 axis x1y1 w steps ls 1 t '%s',\
            '%s' u 1:4 axis x1y1 t '' w p 1,\
            '%s' u 1:4 axis x1y2 w steps ls 2 t '%s',\
            '%s' u 1:4 axis x1y2 t '' w p 2 """ %
                    (f_dat,pvlabel,f_dat,f2_dat,pv2label,f2_dat))
        self.arch.db.use(self.arch.dbname)

        png_size = os.stat(f_png)[6]
        if png_size < 2:
            for i in range(5):
                time.sleep(0.1)
                png_size = os.stat(f_png)[6]
        if png_size > 0:
            self.write("<img src='%s'><br>" % (png_link))
        else:
            self.write("<b>cannot make graph (String Data?)...</b><br>")            
        self.write("<br>%s<br>" % file_link)
        self.write("<a href='%s%sa.gp'>gnuplot script</a><br>" % (self.link_pref,froot))
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

    # set xrange ["2005/08/17 09:00:00":"2005/08/17 14:00:00"]
    def datestring(self,t):
        "return 'standard' date string given a unix timestamp"
        return time.strftime("%Y%m%d %H%M%S",time.localtime(t))        

    def save_data(self,pv,t0,t1,fout,legend):
        "get data from database, save into tmp gnuplot-friendly file"
        dat = self.arch.get_data(pv.pvname,t0,t1)

        pvname = pv.pvname
        # self.write("DATA for PV %s %i  %i" % (pvname,t0,t1))
        # for db in self.arch.master.dbs_for_time(t0,t1):
        # self.write("DATA in %s " % db)

        #  now write data to gnuplot-friendly file
        f = open(fout, 'w')
        f.write("# %s (%s)\n" % (pv.pvname,pv.type))
        f.write("# time_span:  [%s , %s] \n" % (self.datestring(t0),self.datestring(t1)))
        if legend != '':   f.write("# %s \n" % legend)
        f.write("# n_points: %i \n" % len(dat))
        f.write("#-------------------------------\n")
        f.write("#  date      time          value\n")
        for j in dat:
            f.write("%s %i %s\n" % (self.datestring(j[0]), j[0], j[1]))
        f.close()

    def argclean(self,argval,formval):
        v = formval.strip()
        if v != '': return v

        a = argval
        if a is None: a = ''
        if not isinstance(a,str): a = str(a)
        return a.strip()
        
    def show_pv(self,pv=None,pv2=None):
        self.html_title = "GSECARS Data"
   
        arg_pv1 = self.argclean(pv,  self.kw['form_pv'])
        arg_pv2 = self.argclean(pv2, self.kw['form_pv2'])        

        if arg_pv1 != '':
            self.html_title = "%s for %s" % (self.html_title,arg_pv1)
            if not self.in_database(arg_pv1):  self.arch.add_pv(arg_pv1)

        if arg_pv2 != '':
             self.html_title = "%s and %s" % (self.html_title,arg_pv2)
             if not self.in_database(arg_pv2):  self.arch.add_pv(arg_pv2)            
# 
        self.starthtml()
        self.draw_form(arg_pv1,arg_pv2)
        self.endhtml()
        return self.get_buffer()

    

class PV_Admin(HTMLWriter):
    def __init__(self,**kw):
        HTMLWriter.__init__(self)
        self.html_title = "PV Archive Admin Page"
        self.arch   = pvarch.Archiver()
        self.master = pvarch.ArchiveMaster()
        self.cache  = pvcache.PVCache()
        self.kw  = {'form_pv':'', 'submit': '','desc':'','deadtime':'','deadband':'','type':''}
        self.kw.update(kw)

    def show_adminpage(self):
        self.starthtml()
        stat = "<br>&nbsp;&nbsp;&nbsp; ".join(self.master.show_status())
        self.write("Archive Status:<br>&nbsp;&nbsp;&nbsp;  %s<br>" % stat)

        stat = self.arch.cache.cache_status(brief=True)
        self.write("<p>Cache Status: %i new entries in %i seconds, pid=%i<p><hr>" % (len(stat[0]),stat[1],stat[2]))

        pvname = self.kw['form_pv'].strip()
        submit = self.kw['submit'].strip()

        if submit.startswith('Add') and len(pvname)>1:
            sx = pvcache.clean_input(pvname)
            self.write("<p>Adding %s to archive!!<p><hr>" % (sx))
            self.cache.add_pv(sx)
            self.kw['submit'] = ''
            self.kw['form_pv'] = ''
            pvname = ''
            self.endhtml()
            return self.get_buffer()
        
        self.write('<form action ="%s" enctype="multipart/form-data"  method ="POST"><p>' % (adminpage))
        self.write('<p>Search for PV:<input type="text" name="form_pv" value="%s" size=30> (use \'*\' for wildcard searches)</p>' % pvname)

        if pvname != '':
            sx = pvcache.clean_input(pvname.replace('*','%'))
            self.write('<p>Search results for "%s": </p>' % pvname)
                    
            self.master.db.use('pvcache')
            self.master.db.execute('select name from cache where name like %s '% (pvcache.es(sx)))
            results = self.master.db.fetchall()
            i = 0
            for r in results:
                # self.write('<a href="%s?pv=%s">%s</a>&nbsp;&nbsp;'% (thispage,r['name'],r['name']))

                self.write('<a href="%s?pv=%s">%s</a>&nbsp;&nbsp;'% (pvinfopage,r['name'],r['name']))
                i  = i + 1
                if i % 6 == 5: self.write("<br")
                
            if len(results)== 0 and sx.find('%')==-1:
                self.write(" '%s' not found in archive or cache! &nbsp; " % pvname)
                self.write("<input type='submit' name='submit' value='Add to Archive'><p>")
            self.master.db.use('pvarchives')            
                   
        self.endhtml()
        return self.get_buffer()

    def show_pvinfo(self,pv=None,**kw):
        self.kw.update(kw)
        self.starthtml()
        if DEBUG:
            self.write('<p> === Keys: === </p>')
            for key,val in self.kw.items():
                self.write("<p>  %s :  %s </p>" % (key,val))

        if pv is None:
            fpv = self.kw['form_pv'].strip()
            if fpv != '': pv = fpv

        submit = self.kw['submit'].strip()
        es  = pvcache.es
        if submit.startswith('Update') and len(pv)>1:
            pvn = pvcache.clean_input(pv)
            self.write("<p>Updating data for %s!!<p><hr>" % (pvn))
            desc  = pvcache.clean_input(self.kw['desc'].strip())
            dtime = float(pvcache.clean_input(self.kw['deadtime'].strip()))
            dband = float(pvcache.clean_input(self.kw['deadband'].strip()))
            self.arch.db.execute("update PV set DESCRIPTION=%s where PV_NAME=%s" %(es(desc),es(pvn)))
            self.arch.db.execute("update PV set DEADTIME=%s where PV_NAME=%s" %(es(dtime),es(pvn)))
            self.arch.db.execute("update PV set DEADBAND=%s where PV_NAME=%s" %(es(dband),es(pvn)))
                                                                                   
            self.write('<p> <a href="%s?pv=%s">Plot %s</a>&nbsp;&nbsp;</p>'% (thispage,pvn,pvn))
            self.endhtml()
            return self.get_buffer()
        if pv in (None,''):
            self.write("No PV given??")
            self.endhtml()
            return self.get_buffer()            

        self.arch.db.execute("select * from PV where PV_NAME = %s" % (pvcache.es(pv)))
        ret  = self.arch.db.fetchall()
        if len(ret)== 0:
            self.write("PV not in archive??")
            self.endhtml()
            return self.get_buffer()            

        pvn = pvcache.clean_input(pv)
        self.write('<p> <a href="%s?pv=%s">Plot %s</a>&nbsp;&nbsp;</p>'% (thispage,pvn,pvn))
        d = ret[0]
        self.write('<form action ="%s" enctype="multipart/form-data"  method ="POST"><p>' % (pvinfopage))
        self.write('<input type="hidden" name="form_pv" value="%s">' % pvn)
        
        self.write("<table><tr><td>")
        self.write('Description:</td><td><input type="text" name="desc" value="%s" size=30></td>' % d['description'])
        self.write("</tr><tr><td>")
        self.write('Deadtime (seconds):</td><td><input type="text" name="deadtime" value="%s" size=30></td>' % str(d['deadtime']))
        self.write("</tr><tr><td>")
        self.write('Deadband (fraction):</td><td><input type="text" name="deadband" value="%s" size=30></td>' % str(d['deadband']))
        self.write("</tr></table><p><input type='submit' name='submit' value='Update PV Data'><p>")


        self.endhtml()
        return self.get_buffer()


