

from EpicsArchiver import  config
from EpicsArchiver.util import SEC_DAY

cgiroot   = config.cgi_url

thispage   = "%s/viewer.py" % cgiroot
adminpage  = "%s/admin.py" % cgiroot
pvinfopage = "%s/admin.py/pvinfo"       % cgiroot
relpv_page = "%s/admin.py/related_pvs"  % cgiroot
instspage  = "%s/instruments.py"  % cgiroot
statuspage = "%s/status.py" % cgiroot

REFRESH_TIME = "%i" % (SEC_DAY * 7)

htmlhead = """<html>
<head><title>%s</title>
<meta http-equiv='Pragma'  content='no-cache'>
<meta http-equiv='Refresh' content='%s'>
<style type='text/css'>
pre {text-indent: 30px}
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
</style>
%s
</head><body>
"""

jscal_setup = """<link rel='stylesheet' type='text/css' media='all'
 href='%s/calendar-system.css' />
<script type='text/javascript' src='%s/calendar.js'></script>
<script type='text/javascript' src='%s/lang/calendar-en.js'></script>
<script type='text/javascript' src='%s/calendar-setup.js'></script>
"""  % (config.jscal_url, config.jscal_url, config.jscal_url, config.jscal_url)


jscal_get_2dates = """
<script type='text/javascript'>
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
     Calendar.setup({inputField : "date1",   ifFormat   : "%Y-%m-%d %H:%M",
             showsTime  : true,              timeFormat : 24,
             singleClick: false,             button     : "date1_trig",
             weekNumbers: false,             onUpdate   : setdate2  });
     Calendar.setup({inputField : "date2",   ifFormat   : "%Y-%m-%d %H:%M",
             showsTime  : true,              timeFormat : 24,
             singleClick: false,             button     : "date2_trig",
             weekNumbers: false,             });
</script>
"""

jscal_get_date = """
<script type='text/javascript'>
     Calendar.setup({inputField : "date",   ifFormat   : "%Y-%m-%d %H:%M",
             showsTime  : true,             timeFormat : 24,
             singleClick: false,            button     : "date_trig",
             weekNumbers: false,            });
</script>
"""

class HTMLWriter:
    top_links  = ((statuspage, "PV Status", False),
                  (instspage,  "Instruments", True),                  
                  (adminpage,  "Settings / Admin",  True) )
                  

    def __init__(self, **args):
        self.tabledef  ="<table width=90% cellpadding=0 cellspacing=1>"
        self.buffer  = []


    def show_dict(self,d):
        for k,v in d.items():
            self.write("%s= '%s' <br> " % (k,v))

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
        self.write(htmlhead % (self.html_title,refresh,jscal_setup))

    def show_links(self,pv='',**kw):
        self.write("<ul id='tabmenu'>")
        for s in self.top_links:
            link,title,use_pv = s
            if use_pv and pv != '':
                link = "%s?pv=%s" % (link,pv)
            self.write("<li><a  href='%s'>%s</a></li>" % (link,title))

        self.write("</ul><br>")

    def endhtml(self):
        self.write("</body></html>")
