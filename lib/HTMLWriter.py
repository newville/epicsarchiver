

# from EpicsArchiver import  config
# from EpicsArchiver.util import SEC_DAY

import config
import time
from util import SEC_DAY, clean_input, normalize_pvname

adminpage  = "%s/admin.py/" % config.cgi_url
pvinfopage = "%s/admin.py/pvinfo"       % config.cgi_url
relpv_page = "%s/admin.py/related_pvs"  % config.cgi_url
instpage   = "%s/show.py/instrument"  % config.cgi_url
alertspage = "%s/admin.py/list_alerts"   % config.cgi_url
statuspage = "%s/show.py/" % config.cgi_url
helppage   = "%s/help.py/" % config.cgi_url

REFRESH_TIME = "%i" % (SEC_DAY * 7)

conf = {'jscal_url':config.jscal_url,'css_style':config.css_style}

htmlhead = """<html><head><title>%%s</title>
<meta http-equiv='Pragma'  content='no-cache'><meta http-equiv='Refresh' content='%%s'>
%(css_style)s
<link rel='stylesheet' type='text/css' media='all'
 href='%(jscal_url)s/calendar-system.css' />
<script type='text/javascript' src='%(jscal_url)s/calendar.js'></script>
<script type='text/javascript' src='%(jscal_url)s/lang/calendar-en.js'></script>
<script type='text/javascript' src='%(jscal_url)s/calendar-setup.js'></script>
</head>"""  % conf


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
     Calendar.setup({inputField: "date1",button: "date1_trig", onUpdate: setdate2, 
             ifFormat: "%Y-%m-%d %H:%M:%S", showsTime: true,  timeFormat: 24,
             showOthers: true, singleClick: false,  weekNumbers: false});
     Calendar.setup({inputField: "date2",button: "date2_trig", 
             ifFormat: "%Y-%m-%d %H:%M:%S", showsTime: true,  timeFormat: 24,
             showOthers: true, singleClick: false,  weekNumbers: false});
</script>
"""

jscal_get_date = """
<script type='text/javascript'>
Calendar.setup({inputField: "date",button: "date_trig", 
        ifFormat: "%Y-%m-%d %H:%M:%S", showsTime: true,  timeFormat: 24,
        showOthers: true, singleClick: false,  weekNumbers: false});
</script>
"""

class HTMLWriter:
    top_links  = ((statuspage, "PV Status"),
                  (instpage,   "Instruments"),                  
                  (alertspage, "Alerts"), 
                  (adminpage,  "Settings / Admin"),
                  (helppage,   "Help") )

                  
    tabledef  ="<table width=90% cellpadding=0 cellspacing=1>"
    form_start = "<form action='%s' name='%s' enctype='multipart/form-data' method='POST'>"

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

    def setup(self,active_tab=None,formkeys=None,debug=False, helpsection='main', **kw):
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

        self.show_links(pv=pv,inst=inst,help=helpsection,active_tab=active_tab)
        if debug: self.show_dict(self.kw)
        return 

    def starthtml(self,refresh=''):
        if self.html_title in (None,'',' '):  self.html_title = ' '
        if refresh == '' : refresh = REFRESH_TIME
        self.buffer=[]
        self.write(htmlhead % (self.html_title,refresh))
        self.write("<body>")
        self.write("""<table><tr><td align=left width=40%%>
        <font size=+1>%s:</font></td>
        <td align=center width=40%%><font color='#4444AA'>%s</font></td></tr></table><p>
        """ % (config.pagetitle, time.ctime()))

        
    def show_links(self,pv='',inst_id=-1,active_tab=None,**kw):
        self.write("<ul id='tabmenu'>")
        if active_tab is None:  active_tab = "Settings / Admin"
        for s in self.top_links:
            link,title  = s
            is_active = ''
            if active_tab == title:
                is_active = 'class="active"'
            if link == adminpage and pv not in ('',None):
                link = "%s?pv=%s" % (link,pv)
            if link == instpage and inst_id not in (-1,None):
                link = "%s?inst_id=%i" % (link,inst_id)
            if link == helppage and kw.has_key('help'):
                link = "%s?section=%s" % (link,kw['help'])
            
            self.write("<li><a %s href='%s'>%s</a></li>" % (is_active,link,title))
        self.write("</ul><br>")

    def endhtml(self):
        self.write("</body></html>")


    def startform(self, action, name='form', hiddenkeys=None,**kw):
        self.write(self.form_start % (action,name))
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

        print kw
        opts = ['']*ncol
        print opts
        if len(kw)>0:
            for k,v in kw.items():
                if isinstance(v,(tuple,list)):
                    vals = list(v)
                    if len(vals) < ncol: vals.extend(['']*(ncol-len(vals)+2))
                else:
                    vals = [v]*ncol
                for i,o in enumerate(opts):
                    o = "%s %s='%s'" % (o,k,vals[i])
                    opts[i] = o
                #                
#         if kw.has_key('options'): opts = list(kw['options'] )
#         if len(opts)< ncol:
#             opts.extend(['']*(ncol-len(opts)+2))
        print 'opts: ', opts
        
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
    t.addrow('col 1', 'c2', 'c3', align='center',color=('a','b'))

#     t.addrow('span 1 and 2', 'col 3', spans=(2,1))
#     t.addrow('name', t.textinput(name='fnamex'), spans=(1,2))
#     t.addrow('radio', t.radio(name='rx1'), spans=(1,2))

    
    t.endtable()

    print t.get_buffer()
