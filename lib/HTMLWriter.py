

# from EpicsArchiver import  config
# from EpicsArchiver.util import SEC_DAY

import config
from util import SEC_DAY, clean_input, normalize_pvname

adminpage  = "%s/admin.py" % config.cgi_url
pvinfopage = "%s/admin.py/pvinfo"       % config.cgi_url
relpv_page = "%s/admin.py/related_pvs"  % config.cgi_url
instpage   = "%s/show.py/instrument"  % config.cgi_url
alertspage = "%s/admin.py/list_alerts"   % config.cgi_url
statuspage = "%s/show.py" % config.cgi_url
helppage   = "%s/help.py" % config.cgi_url

REFRESH_TIME = "%i" % (SEC_DAY * 7)

htmlhead = """<html>
<head><title>%s</title>
<meta http-equiv='Pragma'  content='no-cache'>
<meta http-equiv='Refresh' content='%s'>
<style type='text/css'>
pre {text-indent: 20px}
h5 {font:bold 14px verdana,arial,sans-serif;color:#042264;}
h4 {font:bold 18px verdana,arial,sans-serif;color:#042264;}
h3 {font:bold 18px verdana,arial,sans-serif;color:#A42424;font-weight:bold;font-style:italic;}
h2 {font:bold 22px verdana,arial,sans-serif;color:#044484;font-weight:bold;}
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
conf = {'jscal_url':config.jscal_url}

jscal_setup = """<link rel='stylesheet' type='text/css' media='all'
 href='%s/calendar-system.css' />
<script type='text/javascript' src='%(jscal_url)s/calendar.js'></script>
<script type='text/javascript' src='%(jscal_url)s/lang/calendar-en.js'></script>
<script type='text/javascript' src='%(jscal_url)s/calendar-setup.js'></script>
"""  % conf


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
            var tunit = Date.MINUTE;
            var tstr = tarr[1].substring(0,2);
            if      (tstr == 'ho'){ tunit= Date.HOUR;   }
            else if (tstr == 'we'){ tunit= Date.WEEK;   }
            else if (tstr == 'da'){ tunit= Date.DAY;   }
            else if (tstr == 'mo'){ tunit= Date.DAY*31; }
            time     += tarr[0] * tunit; 
            var date2 = new Date(time);
            f2.value  = date2.print("%Y-%m-%d %H:%M:%S");
          }
     }
     Calendar.setup({inputField : "date1",   ifFormat   : "%Y-%m-%d %H:%M:%S",
             showsTime  : true,              timeFormat : 24,
             singleClick: false,             button     : "date1_trig",
             weekNumbers: false,             onUpdate   : setdate2  });
     Calendar.setup({inputField : "date2",   ifFormat   : "%Y-%m-%d %H:%M:%S",
             showsTime  : true,              timeFormat : 24,
             singleClick: false,             button     : "date2_trig",
             weekNumbers: false,             });
</script>
"""

jscal_get_date = """
<script type='text/javascript'>
Calendar.setup({inputField : "date",   ifFormat   : "%Y-%m-%d %H:%M:%S",
             showsTime  : true,             timeFormat : 24,
             singleClick: false,            button     : "date_trig",
             weekNumbers: false,            });
</script>
"""

class HTMLWriter:
    top_links  = ((statuspage, "PV Status"),
                  (instpage,   "Instruments"),                  
                  (alertspage, "Alerts"), 
                  (adminpage,  "Settings / Admin"),
                  (helppage,   "Help") )

                  
    tabledef  ="<table width=90% cellpadding=0 cellspacing=1>"
    form_start = "<form action='%s' enctype='multipart/form-data' method='POST'>"

    def __init__(self, **args):
        
        self.buffer  = []
        self.kw      = {}
        self.ncol    = []
        
    def write(self,s):
        self.buffer.append(s)

    def get_buffer(self):
        r = '\n'.join(self.buffer)
        self.buffer =[]
        return r

    def show_dict(self,d):
        self.write(' <p> Passed Parameters:</p>')
        for k,v in d.items():
            self.write("%s= '%s' <br> " % (k,v))                    
        self.write(' <p> =============== </p>')            

    def setup(self,formkeys=None,debug=False, helpsection='main', **kw):
        """ update self.kw with passed keywords, using
        'web form' versions as defaults (see below). Also
        starts the html and shows starting links

        For each key in formkeys:
            if the self.kw has an empty value ('' or None)
            the 'form_%s' % key is used as a default value
            and self[key] is set to the 'form_%s' version

        """
        self.kw.update(kw)
        if formkeys is not None and len(formkeys)>0:
            for key in formkeys:
                val = clean_input(self.kw.get(key,''))
                if val == '':
                    val = clean_input(self.kw.get("form_%s" % key,''))
                    if val != '':
                        self.kw[key] = val

        self.starthtml()

        inst = self.kw.get('inst_id',-1)
        pv = self.kw.get('pv','')
        pv = normalize_pvname(pv)
            
        self.show_links(pv=pv,inst=inst,help=helpsection)
        if debug: self.show_dict(self.kw)
        return 

    def starthtml(self,refresh=''):
        if self.html_title in (None,'',' '):  self.html_title = ' '
        if refresh == '' : refresh = REFRESH_TIME
        self.write(htmlhead % (self.html_title,refresh,jscal_setup))

    def show_links(self,pv='',inst_id=-1,**kw):
        self.write("<ul id='tabmenu'>")
        for s in self.top_links:
            link,title  = s
            if link == adminpage and pv not in ('',None):
                link = "%s?pv=%s" % (link,pv)
            if link == instpage and inst_id not in (-1,None):
                link = "%s?inst_id=%i" % (link,inst_id)
            if link == helppage and kw.has_key('help'):
                link = "%s?section=%s" % (link,kw['help'])
            
            self.write("<li><a  href='%s'>%s</a></li>" % (link,title))
        self.write("</ul><br>")

    def endhtml(self):
        self.write("</body></html>")


    def startform(self, action, hiddenkeys=None,**kw):
        self.write(self.form_start % action)
        if hiddenkeys is not None:
            for key in hiddenkeys:
                self.write(self.hiddeninput(name="form_%s" % key,
                                            value= self.kw.get(key,'')))

    def endform(self, **kw):
        self.write("</form>")

    def starttable(self,ncol=2,**kw):
        self.ncol.append(ncol)
        s = []
        for k,v in kw.items():
            s.append(self._make_keyval(k,v))

        s = ' '.join(s).strip()
        self.write("<table %s>" % s)
        
    def addrow(self,*args,**kw):
        try:
            ncol = self.ncol[-1]
        except IndexError:
            ncol = 1

        nargs = len(args)
        
        spans = [1]*ncol
        if kw.has_key('spans'): spans = list(kw['spans'])
        if len(spans)< ncol:
            spans.extend(['']*(ncol-len(spans)+2))

        opts = ['']*ncol
        if kw.has_key('options'): opts = list(kw['options'] )
        if len(opts)< ncol:
            opts.extend(['']*(ncol-len(opts)+2))

        self.write("<tr>")
        wr = self.write
        mcol = 0
        for iarg in range(min(nargs,ncol)):
            if spans[iarg] == 1:
                wr("<td %s>%s</td>" % (opts[iarg],args[iarg]))
                mcol = mcol + 1
            else:
                wr("<td %s colspan=%i>%s</td>" % (opts[iarg],spans[iarg],args[iarg]))
                mcol = mcol + spans[iarg]
                
        if ncol > mcol:
            for i in range(ncol-mcol):
                wr("<td></td>")
        wr("</tr>")
        
    def endtable(self):
        self.ncol.pop()
        self.write("</table>")

    def _make_keyval(self,k,v):
        "make a key/val pair for html"
        istyped = False
        fmt="%s='%s'"
        if isinstance(v,(int,long)):      fmt,istyped = "%s=%i",True
        elif isinstance(v,(float)):       fmt,istyped = "%s=%i",True
        elif isinstance(v,(str,unicode)): fmt,istyped = "%s='%s'",True
        
        if not istyped: v = str(v)
        return fmt % (k,v)
    

    def _input(self,type='text',**kw):
        s = ["<input type='%s'" % type]
        if 'radio' == type and kw.has_key('checked'):
            r_checked = kw.pop('checked')
            if r_checked:  s.append("checked='true'")
            
        for k,v in kw.items():
            s.append(self._make_keyval(k,v))
        s.append("/>")
        return " ".join(s)
        
    def textinput(self,name='text',value='',size=30,nlines=1,id=None,**kw):
        if id is None: id=name
        if nlines <= 1:
            return self._input(type='text',id=id,name=name,value=value,size=size,**kw)
        else:
            s = ' '.join([self._make_keyval('name',name),
                          self._make_keyval('id',  id),
                          self._make_keyval('rows',nlines),                          
                          self._make_keyval('cols',size)])
            
            return '<textarea %s>%s</textarea>' % (s,value)

    def hiddeninput(self,name='text',value='',**kw):
        return self._input(type='hidden',name=name,value=value,**kw)
                
    def radio(self,checked=False,name='choice',value='choice',text=None,**kw):
        if text is None: text = value
        return "%s %s" % (self._input(type='radio',checked=checked,
                                     name=name,value=value,**kw), text)

    def button(self,text='Submit',**kw):
        """sumbit button: use existence of keyword 'value' to determine
        which button was submitted"""
        return self._input(type='submit',name='submit',value=text,**kw)

    def link(self,link='',text='',**kw):
        return "<a href='%s'>%s</a>" % (link,text)

    def select(self,id='selection',name='selection',default=None,choices=None,**kw):
        s = ["<select id='%s' name='%s'>" % (id,name)]
        if choices is not None:
            for i in choices:
                xtra = ''
                if i == default: xtra = 'selected'
                s.append("<option %s value='%s'>%s\n" % (xtra,i,i))
        s.append("</select>")
        return " ".join(s)
        
        

if __name__ == '__main__':
    t = HTMLWriter()
    t.starttable(ncol=3)
    t.addrow('col 1', 'c2', 'c3')

    t.addrow('span 1 and 2', 'col 3', spans=(2,1))
    t.addrow('name', t.textinput(name='fnamex'), spans=(1,2))
    t.addrow('radio', t.radio(name='rx1'), spans=(1,2))

    
    t.endtable()

    print t.get_buffer()
