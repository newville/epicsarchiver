#!/usr/bin/env python

import time
from EpicsArchiver import Cache, config
from util import normalize_pvname
pagetitle  = config.pagetitle
footer     = config.footer

statpage   = "%s/show.py/show_page"    % config.cgi_url
instpage   = "%s/show.py/instrument"   % config.cgi_url
dblink     = "%s/show.py/plot?pv="     % config.cgi_url
alertspage = "%s/admin.py/list_alerts" % config.cgi_url
adminpage  = "%s/admin.py/"             % config.cgi_url
helppage   = "%s/help.py?section=templates"  % config.cgi_url

htmlhead = """<html>
<head><title>%s</title><meta http-equiv='Pragma'  content='no-cache'><meta http-equiv='Refresh' content=%s>
%s</head>"""

class WebStatus:
    table_def   = "<table width=90% cellpadding=1 border=0 cellspacing=2>"    
    hrule_row   = "<tr><td colspan=2> <hr>   </td></tr>"
    space_row   = "<tr><td colspan=2> &nbsp; </td></tr>"
    normal_row  = "<tr><td><b>%s</b></td><td>%s</td></tr>"
    colored_row = "<tr><td><b>%s</b></td><td><font color=%s> %s </font></td></tr>"
    title_row   = "<tr><th colspan=2><font color=%s>%s</font></tr>"
    
    def __init__(self,cache=None,dbconn=None,**kw):
        if cache is None:
            cache = Cache(dbconn=dbconn)
        self.cache  = cache
        self.dbconn = self.cache.dbconn
        self.pvget  = self.cache.get_full
        self.null_pv= self.cache.null_pv_value
        self.dat_cached = {}
        self.dat_time   = -1

        self.dblink    = dblink
        self.valcolor  = '#5522DD'
        self.titlecolor= '#116644'
        self.labelcolor= '#DD2233'
        self.buffer  = []

    def write(self,s):  self.buffer.append(s)

    def get_buffer(self):
        r = '\n'.join(self.buffer)
        self.buffer = []
        return r

    def get_pv(self,pv,format=None,desc=None,outtype=None):
        """ get cached value for a PV, formatted """
        if (time.time()-self.dat_time ) > 10.0:
            self.dat_time = time.time()
            self.dat_cached = {}
            for i in self.cache.cache.select():
                self.dat_cached[i['pvname']] = i
            
        ret = self.dat_cached.get(pv,None)
        if ret is None:
            self.pvget(pv,add=True)
            if desc is None: desc = pv
            return (desc,'Unknown')
            
        oval = ret['cvalue']
        val  = ret['value']
                
        try:
            if format is not None :
                oval = format % float(val)
        except:
            pass

        if desc is None:
            idot   = pv.find('.')
            if idot == -1: idot = len(pv)
            descpv = "%s.DESC" % pv[:idot]
            rx = self.dat_cached.get(descpv,None)
            if rx is not None:
                desc = rx['cvalue']
            else:
                rx = self.pvget(descpv,add=True)
                if rx is not self.null_pv:
                    desc = rx['cvalue']
                
        if desc in (None, ''): desc = pv
        if outtype=='yes/no':
            oval = 'Unknown'
            try:
                if int(float(val.strip())) == 0: oval = 'No'
                if int(float(val.strip())) == 1: oval = 'Yes'
            except ValueError:
                pass
        return (desc,oval)

    def show_pv(self,pv,format=None,desc=None,type=None):    
        desc,val = self.get_pv(pv,format=format,desc=desc,outtype=type)
        self.linked_row(desc,pv,"%s" %val)

    def start_table(self,title=None):
        self.write("%s %s" %(self.table_def,self.space_row))
        if title:
            self.write(self.title_row % (self.titlecolor,title))

    def end_table(self):
        self.write("</table><br>")
            
    def linked_row(self,label,pvnames,vals):
        if isinstance(pvnames,(tuple,list)) and isinstance(vals,(tuple,list)):
            outlinks = []
            for name,val in zip(pvnames,vals):
                name = name.strip()
                if val is None: val = 'NONE_Unknown'
                outlinks.append( self.archlink(name,val))
            outval =  ',&nbsp; '.join(outlinks)
            if isinstance(label,(tuple,list)):
                label = ',&nbsp;'.join(label)

            self.row(label,outval)
        else:  # single pv/val:
            if vals is None: vals = 'SINGLE_Unknown'
            v = "<a href='%s%s'>%s</a>" % (self.dblink,pvnames,vals)
            self.row(label,v)            
            

    def row(self,name,val):
        self.write(self.colored_row % (name,self.valcolor,val))

    def table_entry(self,nam,val):
        self.write(self.normal_row % (nam,val))

    def table_label(self,label):
        x = "<font color=%s>%s</font>" % (self.labelcolor,label)
        self.table_entry(x,"");

    #     
    def show_pvfile(self,file):
        try:
            f = open(file,"r")
            lines = f.readlines()
            f.close()
        except:
            lines = ['','']
        for s in lines:
            s = s.strip()
            if len(s) < 1: continue
            
            if s.startswith('#') or len(s) < 2:
                continue
            elif s.startswith('['):
                i = s.find(']')
                if i == -1: i= len(s)
                self.table_label(s[1:i])
            elif s.startswith('--'):
                self.write(self.hrule_row)
            elif s.startswith('<>'):
                self.write(self.space_row)
            else:
                cline = s.split('|')
                pvnames = []
                try:
                    for i in cline.pop(0).strip().split(','):
                        pvnames.append(normalize_pvname(i.strip()))

                except:
                    pass
                try:
                    desc   = cline.pop(0).strip()
                    if len(desc)==0: desc = None
                except:
                    desc  = None
                try:
                    format = cline.pop(0).strip()
                except:
                    format = None
                outtype=None
                if format == 'yes/no':
                    format = None
                    outtype = 'yes/no'
                    
                if pvnames != []:
                    vals = []
                    labs = []
                    for pvname in pvnames:
                        # pvname = pvname.strip()
                        (label,val) =  self.get_pv(pvname,format=format,desc=desc,outtype=outtype)
                        # self.write("<tr>  <td>:: %s</td><td>%s</td></tr>" % (pvname,str(val)))

                        if (label is None): label = pvname
                        if (label.startswith('"') and label.endswith('"') or
                            label.startswith("'") and label.endswith("'")):
                            label = label[1:len(label)-1]
                        labs.append(label)
                        vals.append(val)
                    if len(pvnames) > 1:
                        if desc is None: desc = labs
                        self.linked_row(desc,pvnames,vals)
                        self.cache.set_allpairs(pvnames)
                    else:
                        if desc is None: desc = labs[0]
                        self.linked_row(desc,pvnames[0],vals[0])
                        

    def remove_quotes(self, str):
        s = str.strip()
        if (s == ''): return None
        if (len(s) > 2):
            if ( ((s[0] == "'") and (s[-1] == "'" )) or
                 ((s[0] == '"') and (s[-1] == '"' )) ):
                s = s[1:len(s)-1]
        return s
    # 
    
    def begin_page(self,page,pagelist,refresh=12):
        self.write(htmlhead % (pagetitle, refresh,config.css_style)) #
        self.write("""<table><tr><td align=left width=40%%>
        <font size=+1>%s:</font></td><td align=center width=40%%><font color='#4444AA'>%s</font></td>
        <td align=rignt><a href='%s'>Settings/Admin</a></td>
        <td align=rignt><a href='%s'>Help</a></td></tr></table><p>""" % (config.pagetitle,
                                                                         time.ctime(), adminpage,
                                                                         helppage))

        self.write("<body><ul id='tabmenu'>")
        for i in pagelist:
            s = ''
            if i == page: s = 'class="active"'
            self.write("""<li><a %s href='%s?page=%s'>%s</a></li>"""
                     % (s,statpage,i,i))

        self.write("<li><a href='%s'>Instruments</a></li>" % (instpage))
        # self.write("<li><a href='%s'>Alerts</a></li>" % (alertspage))
        # self.write("<li><a href='%s'>Admin</a></li>" % (adminpage))
        # self.write("<li><a href='%s'>Help</a></li>" % (helppage))
        self.write("</ul>")
        self.start_table()


    def end_page(self,show_stats=False,msg=''):
        self.end_table()
        self.write(msg)
        self.write(footer)
        self.write("</p></body></html>""")

    def archlink(self,pv,val):
        return "<a href='%s%s'>%s</a>" % (dblink,pv,val)

    ###
    ### Vacuum Tables: specialized to GSECARS-like vacuum system -- using a 4 column table...
    ### 
    def start_table_vac(self,title='Table'):
        self.write("%s %s" %(self.table_def,self.space_row))
        self.write("<tr><th colspan=4><font color=%s>%s</font></tr>" % (self.titlecolor,title))

    def vac_table(self,pv,cc_pr=(None,None), label=None,type='GSE'):
        ionpump_pvs  = {'GSE': ('_Volts.VAL','_Current.VAL','_Pressure.VAL'),
                        'GSE2':(':VOLT.VAL',':CUR.VAL',':PRES.VAL'),
                        'APS': ('.VOLT','.CRNT','.VAL') }


        tags = ionpump_pvs['GSE']
        if (ionpump_pvs.has_key(type)):  tags = ionpump_pvs[type]
        vpv = "%s%s" % (pv, tags[0])
        ipv = "%s%s" % (pv, tags[1])
        ppv = "%s%s" % (pv, tags[2])
        dv,v = self.get_pv(vpv,format='%9.0f')
        di,i = self.get_pv(ipv,format='%9.2e')
        dp,p = self.get_pv(ppv,format='%9.2e')
        pumpdat = "<td><a href='%s%s'>%s</a>(<a href='%s%s'>%s</a>, <a href='%s%s'>%s</a>)</td>"  %\
                  (self.dblink,ppv,p,self.dblink,vpv,v,self.dblink,ipv,i)

        guagedat = "<td></td>"
        if (cc_pr != (None,None)):
            prpv  = "%s:pr%1.1i.VAL" % cc_pr
            ccpv  = "%s:cc%1.1i.VAL" % cc_pr  
            dpr,pr = self.get_pv(prpv,format='%9.2e')
            dcc,cc = self.get_pv(ccpv,format='%9.2e')
            if (pr == None): pr = 0.0
            if (cc == None): cc = 0.0
            guagedat = "<td><a href='%s%s'>%s</a> (<a href='%s%s'>%s</a>)</td>"  % \
                       (self.dblink,ccpv,cc, self.dblink,prpv,pr)

        self.write("<tr><td><b>%s</b></td><td></td>%s %s</tr>" % (label,guagedat,pumpdat))

    def vac_pirani(self,label,pv,format="%8.2e"):
        (name,v) = self.get_pv(pv,format=format)
        self.write("<tr>  <td><b>%s</b></td><td></td>" % (label)        )
        self.write("<td><a href='%s%s'>%s</a></td><td></td>" % (self.dblink,pv,v))
        self.write("</tr>")

    def table_entry_vac_title(self,vals):
        self.write("<tr>")
        for i in vals:
            self.write("  <td>%s</td>" % (i))
        self.write("<tr>")

    def table_label_vac(self,label):
        self.write("<tr><td><hr></td><td><font color=%s>%s</td><td colspan=2><hr></td></tr>" % (self.labelcolor,label))

    def valve_row(self,pv,label):
        p = "%s_status.VAL" % (pv)
        (d,v) =self.get_pv(p)
        self.write("""<tr><td><b>%s</b></td><td><font color=%s>
        <a href='%s%s'>%s</a></td>
        <td colspan=2></td></tr>"""  % (label,self.valcolor,self.dblink,p,v))


    def show_bmvac(self):
        self.table_entry_vac_title(("Component","Status", "Pressure CC (Pirani)", "Ion Pump Pressure (V,I)"))
        # BM A
        self.table_label_vac("13 BM A")
        self.show_pv("PA:13BM:Q01:00.VAL", desc = "Station Searched")

        self.vac_table("13BMA:ip1",label='Slit Tank',        type='GSE',  cc_pr=("13BMA",1))
        self.valve_row("13BMA:BMD_BS",'BMD White Beam Stop')
        self.valve_row("13BMA:BMC_BS",'BMC White Beam Stop')
        self.valve_row("13BMA:V1",'Valve 1')
        self.vac_table("13BMA:ip2",label='Mono Tank',        type='GSE',  cc_pr=("13BMA",2))
        self.valve_row("13BMA:V2",'Valve 2')
        self.vac_table("13BMA:ip1",label='Diagnostic Tank',   type='GSE',  cc_pr=("13BMA",3))
        self.valve_row("13BMA:V3",'Valve 3')

        # BM B
        self.table_label_vac("13 BM B")
        self.show_pv("PA:13BM:Q01:01.VAL", desc = "Station Searched")
        self.vac_table("13BMA:ip7",label='BMC Slit Tank',     type='GSE',  cc_pr=("13BMA",7))
        self.valve_row("13BMA:V4C",'BMC Valve 4')
        self.vac_table("13BMA:ip8",label='BMC Mono Tank',      type='GSE2',   cc_pr=("13BMA",8))
        self.show_pv("13BMA:eps_mbbi100.VAL")

        self.valve_row("13BMA:V4D",'BMD Valve 4')
        self.vac_table("13BMA:ip9",label='BMD Mirror Tank',   type='GSE2',  cc_pr=("13BMA",4))
        self.show_pv("13BMA:eps_mbbi99.VAL")

        # BM C
        self.table_label_vac("13 BM C")
        self.show_pv("PA:13BM:Q01:02.VAL", desc = "Station Searched")
        # BM D
        self.table_label_vac("13 BM D")
        self.show_pv("PA:13BM:Q01:03.VAL", desc = "Station Searched")
        self.vac_table("13BMA:ip10",label='BMD Slit Tank',
                       type='GSE',  cc_pr=("13BMA",9))
        self.vac_pirani("Flight Tube","13BMA:pr10.VAL")


    def show_idvac(self):
        self.table_entry_vac_title(("Component","Status",
                             "Pressure CC (Pirani)", "Ion Pump Pressure (V,I)"))
        # ID A
        self.table_label_vac("13 ID A")
        self.show_pv("PA:13ID:Q01:00.VAL", desc = "Station Searched")

        self.vac_table("FE:13:ID:IP7",label="Differential Pump",type='APS')


        self.valve_row("13IDA:V1",'Valve 1')
        self.vac_table("13IDA:ip1",label='Slit Tank',     type='GSE',  cc_pr=("13IDA",1))
        self.valve_row("13IDA:V2",'Valve 2')
        self.vac_table("13IDA:ip2",label='Mono Tank',     type='GSE2',  cc_pr=("13IDA",2))

        self.valve_row("13IDA:V3",'Valve 3')
        self.vac_table("13IDA:ip1",label='Pinhole Tank',  type='GSE',  cc_pr=("13IDA",3))

        self.valve_row("13IDA:BS",'White Beam Stop')
        self.valve_row("13IDA:V4",'Valve 4')
        self.vac_table("13IDA:ip3",label='Pumping Cross 1',     type='GSE')

        # ID B
        self.table_label_vac("13 ID B")
        self.show_pv("PA:13ID:Q01:01.VAL", desc = "Station Searched")
        self.vac_table("13IDA:ip5",label='Pumping Cross 2',    type='GSE',  cc_pr=("13IDA",5))
        self.valve_row("13IDA:V5",'Be Bypass #1')
        self.vac_table("13IDA:ip6",label='Vertical Mirror',    type='GSE2',  cc_pr=("13IDA",7))
        self.vac_table("13IDA:ip7",label='Horizontal  Mirror', type='GSE2')
        self.valve_row("13IDA:V6",'Be Bypass #2')

        self.vac_pirani("Flight Tube","13IDA:pr6.VAL")
        self.vac_pirani("BPM battery Voltage" ,  "13IDA:DMM2Ch9_raw.VAL",format = "%8.3f")

            
