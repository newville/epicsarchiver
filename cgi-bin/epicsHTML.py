#!/usr/bin/env python

import pvcache
normalize = pvcache.normalize_pvname

import time
import os
import sys
import types


TEST = False

title      = "GSECARS Beamline Status Page"
homepage   = "http://cars9.uchicago.edu/gsecars/"
cgiroot    = "http://cars9.uchicago.edu/cgi-bin/gse_status"

if TEST:
    title   = "GSECARS Beamline Status Page (TEST!)"
    cgiroot = "http://millenia.cars.aps.anl.gov/~newville/py"
    

thispage = "%s/status.py" % cgiroot
dblink   = "%s/archiver.py?pv=" % cgiroot

footer = """<hr>[
<a href=http://cars9.uchicago.edu/gsecars  target='_top'>GSECARS</a> |
<a href=http://cars9.uchicago.edu/gsecars/webcam> Beamline Web Cameras</a> |
<a href=http://www.aps.anl.gov/asd/operations/gifplots/statgif.html>APS Status</a> |
<a href=http://www.aps.anl.gov/>APS</a> ]"""


pages = ('General', 'Storage Ring', 'ID Mono', 'ID Vacuum',
         'ID Water', 'BM Mono', 'BM Vacuum', 'BM Water', 'ID C')

stations = ('BM D', 'ID C', 'ID D')

tabs   = {'General':'t1',
          'Storage Ring':'t2',
          'ID Mono':'t3',
          'BM Mono':'t4',
          'ID Vacuum':'t5',
          'BM Vacuum':'t6',
          'ID Water':'t7',
          'BM Water':'t8',
          'BM D':'t9',
          'ID C':'t10',
          'ID D':'t11'}

style = """
h4 {font: bold 18px verdana, arial, sans-serif;
    color: #044484; font-weight: bold; font-style: italic;}

pre {text-indent: 30px}

body {margin: 20px; padding: 0px;
      background: #FCFCEA;
      font: bold 14px verdana, arial, sans-serif;}

#content {text-align: justify;
      background: #FCFCEA;
      padding: 0px;
      border: 4px solid #88000;
      border-top: none;
      z-index: 2;	}

#tabmenu {
font: bold 11px verdana, arial, sans-serif;
border-bottom: 2px solid #880000;
margin: 1px;
padding: 0px 0px 4px 0px;
padding-left: 20px}

#tabmenu li {
display: inline;
overflow: hidden;
margin: 1px;
list-style-type: none; }

#tabmenu a, a.active {
color: #4444AA;
background: #EEDD88;
border: 2px solid #880000;
padding: 3px 3px 4px 3px;
margin: 0px ;
text-decoration: none; }

#tabmenu a.active {
color: #CC0000;
background: #FCFCEA;
border-bottom: 2px solid #FCFCEA;
}

#tabmenu a:hover {color: #CC0000; background: #F9F9E0;}
"""

class epicsHTML:
    ionpump_pvs  = {'GSE': ('_Volts.VAL','_Current.VAL','_Pressure.VAL'),
                    'GSE2':(':VOLT.VAL',':CUR.VAL',':PRES.VAL'),
                    'APS': ('.VOLT','.CRNT','.VAL') }

    def __init__(self,**args):
        self.tabledef  ="<table width=90% cellpadding=1 cellspacing=2>"
        self.dblink    = dblink

        self.pvcache = pvcache.PVCache()
        self.cursor  = self.pvcache.cursor
        self.pvget   = self.pvcache.get_full

        self.valcolor  = '#5522DD'
        self.titlecolor= '#116644'
        self.labelcolor= '#DD2233'
        self.buffer  = []

    def write(self,s):
        self.buffer.append(s)

    def get_buffer(self):
        r = '\n'.join(self.buffer)
        self.buffer = []
        return r

    def starthtml(self):
        self.write("""<?xml version='1.0' encoding='utf-8'?>
        <!DOCTYPE html PUBLIC '-//W3C//DTD XHTML Basic 1.0//EN'
        'http://www.w3.org/TR/xhtml-basic/xhtml-basic10.dtd' """)

    def get_pv(self,pv,format=None,desc=None,outtype=None):
        if True:# try:
            ret = self.pvget(pv,add=True)
            # val,cval,dtype,ts = self.pvget(pv,add=True)
            oval = ret['cvalue']
            if ret == pvcache.null_pv_value:
                if desc is None: desc = pv
                return (desc,'Unknown(1)')

            val  = ret['value']
            cval = ret['cvalue']
            dtype= ret['type']
            ts   = ret['ts']
            try:
                xx = float(val)
                isnum = True
            except:
                isnum = False


            if format is not None and isnum:
                try:
                    oval = format % float(val)
                except:
                    pass
                    
            if desc is None:
                idot   = pv.find('.')
                if idot == -1: idot = len(pv)
                descpv = "%s.DESC" % pv[:idot]
                try:
                    rx = self.pvget(descpv,add=True)
                    desc = rx['cvalue']
                except:
                    pass # desc = '%s' % pv
            if desc is None: desc = pv
            if outtype=='yes/no':
                oval = 'Unknown'
                if int(float(val.strip())) == 0: oval = 'No'
                if int(float(val.strip())) == 1: oval = 'Yes'
            return (desc,oval)
        else: # except:
            if desc is None: desc = pv
            return (desc,'Unknown2')
        
    def add_pv(self,pv,format=None,desc=None,type=None):    
        desc,val = self.get_pv(pv,format=format,desc=desc,outtype=type)
        self.add_table_row_link(desc,pv,"%s" %val)

    def add_mbbi(self,pv,desc=None):
        self.add_pv(pv,desc=desc)

    def add_mbbis(self,pvs):
        for pv in pvs:  self.add_pv(pv,desc=None)

    def start_table(self,title=None):
        self.write("%s<tr><td></td><td></td></tr>" %self.tabledef)
        if title:
            self.write("<tr><th colspan=2><font color=%s>%s</font></tr>" % (self.titlecolor,title))

    def start_table_vac(self,title='Table'):
        self.write("%s<tr><td></td><td></td></tr>" % self.tabledef)
        self.write("<tr><th colspan=4><font color=%s>%s</font></tr>" % (self.titlecolor,title))
            
    def end_table(self):
        self.write("</table><br>")
            

    def add_table_row_link(self,name,pv,val):
        v = "<a href='%s%s'>%s</a>" % (self.dblink,pv,val)
        self.add_table_row(name,v)
        
    def add_table_row(self,name,val):
        self.write("""<tr><td><b>%s</b></td><td><font color=%s> %s </font></td></tr>"""  % (name,self.valcolor,val))


    def table_entry(self,nam,val):
        self.write("<tr><td><b>%s</b></td><td>%s</td>" % (nam,val))

    def table_label(self,label):
        x = "<font color=%s>%s</font>" % (self.labelcolor,label)
        self.table_entry(x,"");


    def end_table_vac(self):
        self.end_table()

    def vac_table(self,pv,cc_pr=(None,None), label=None,type='GSE'):
        tags = self.ionpump_pvs['GSE']
        if (self.ionpump_pvs.has_key(type)):  tags = self.ionpump_pvs[type]
        vpv = "%s%s" % (pv, tags[0])
        ipv = "%s%s" % (pv, tags[1])
        ppv = "%s%s" % (pv, tags[2])
        dv,v = self.get_pv(vpv,format='%9.0f')
        di,i = self.get_pv(ipv,format='%9.2e')
        dp,p = self.get_pv(ppv,format='%9.2e')
        pumpdat = "<td><a href='%s%s'>%s</a>  (<a href='%s%s'>%s</a>, <a href='%s%s'>%s</a>)</td>"  %\
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
        self.write("  <td><a href='%s%s'>%s</a></td><td></td>" % (self.dblink,pv,v))
        self.write("</tr>")

    def table_entry_vac_title(self,vals):
        self.write("<tr>")
        for i in vals:
            self.write("  <td>%s</td>" % (i))
        self.write("<tr>")

    def table_label_vac(self,label):
        self.write("<tr><td><hr></td><td><font color=%s>%s</td><td colspan=2><hr></td></tr>" % (self.labelcolor,label))

    def add_valve(self,pv,label):
        p = "%s_status.VAL" % (pv)
        (d,v) =self.get_pv(p)
        self.write("""<tr><td><b>%s</b></td><td><font color=%s>
        <a href='%s%s'>%s</a></td>
        <td colspan=2></td></tr>"""  % (label,self.valcolor,self.dblink,p,v))


    #     
    def add_pvfile(self,file):
        from getopt import getopt
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
            else:
                cline = s.split('|')
                try:
                    pvname = cline.pop(0).strip()
                except:
                    pvname = None
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
                    
                if pvname is not None:
                    (label,val) =  self.get_pv(pvname,format=format,desc=desc,outtype=outtype)
                    if (label is None): label = pvname
                    if label.startswith('"') and label.endswith('"') : label = label[1:len(label)-1]
                    if label.startswith("'") and label.endswith("'") : label = label[1:len(label)-1]
                    if (val == None): val = 'Unknown'
                    self.add_table_row_link(label,pvname,val)

    def remove_quotes(self, str):
        s = str.strip()
        if (s == ''): return None
        if (len(s) > 2):
            if ( ((s[0] == "'") and (s[-1] == "'" )) or
                 ((s[0] == '"') and (s[-1] == '"' )) ):
                s = s[1:len(s)-1]
        return s
    # 
    
    def begin_page(self,page,refresh=12):
        self.starthtml()
        self.write("<html><head><title>%s</title>" % title)
        self.write('<meta http-equiv="Pragma"  content="no-cache">')
        self.write('<meta http-equiv="Refresh" content=%s>' % refresh)
        self.write('<style type="text/css">%s</style></head>' %  style)
        self.write("<body>") #  % tabs[page])
        self.write("<h4>%s&nbsp;&nbsp;&nbsp;&nbsp; %s</h4>" % (title,time.ctime()))
        self.write("<ul id='tabmenu'>")
        for i in pages:
            s = ''
            if i == page: s = 'class="active"'
            self.write("""<li><a %s href='%s/show_page?page=%s'>%s</a></li>"""
                     % (s,thispage,i,i))
        self.write("</ul><br>")
        self.start_table()


    def end_page(self,show_stats=False,msg=''):
        self.end_table()
        self.write(msg)
        self.write(footer)
        self.write("</p></body></html>""")

    def archlink(self,pv,val):
        return "<a href='%s%s'>%s</a>" % (dblink,pv,val)

    def show_general(self):
        self.table_label("Storage Ring")
        self.add_pv("BL13:ActualMode.VAL")
        self.add_pv("BL13:srCurrent.VAL",   format = "%8.3f")
        self.add_pv("BL13:srLifetime.VAL",  format = "%8.3f")
        self.add_pv("13IDA:eps_bo1.VAL",    desc= 'Shutter Permit')

        self.table_label("ID EPS")
        self.add_pv("13IDA:eps_mbbi57",  desc= 'Front End Valve')
        self.add_pv("13IDA:eps_mbbi4",   desc= 'Front End Shutter')
        self.add_pv("13IDA:eps_mbbi81",  desc= 'Vacuum Status')
        self.add_pv("13IDA:eps_mbbi5",   desc= 'EPS Status')
        self.add_pv("13IDA:BS_status",   desc= 'White Beam Stop')

        self.table_label("BM EPS")
        self.add_pv("13BMA:eps_mbbi42",  desc= 'Front End Valve')
        self.add_pv("13BMA:eps_mbbi4",   desc= 'Front End Shutter')
        self.add_pv("13BMA:eps_mbbi5",   desc= 'EPS Status')        

        self.table_label("Air Temperatures")
        self.add_pv("G:AHU:FP5088Ai.VAL", desc= '13IDD Air Temp (F)', format = "%8.3f")
        self.add_pv("G:AHU:FP5087Ai.VAL", desc= '13IDC Air Temp (F)', format = "%8.3f")
        self.add_pv("G:AHU:FP5095Ai.VAL", desc= '13BMD Air Temp (F)', format = "%8.3f")
        self.add_pv("G:AHU:FP5097Ai.VAL", desc= 'Roof  Air Temp (F)', format = "%8.3f")

        self.table_label("Configuration")

        # stations searched
        for label,h in (('ID',"PA:13ID:Q01:0%i.VAL"),('BM',"PA:13BM:Q01:0%i.VAL")):
            val = "("
            for i in range(4):
                t  = 'No'
                pv = h % i
                (d1,m1) = self.get_pv(pv)
                if m1.startswith('Searched'):  t= "Yes"
                val = "%s%s," % (val,self.archlink(pv,t))
            val = val[:-1] + ')'
            self.add_table_row("%s Stations Searched (A,B,C,D)" % label,val)

        # gas tanks
        (d1,m1) = self.get_pv("13IDA:eps_mbbi67.VAL")
        (d2,m2) = self.get_pv("13IDA:eps_mbbi68.VAL")
        val = "(%s,%s)" % (self.archlink("13IDA:eps_mbbi67.VAL",m1),self.archlink("13IDA:eps_mbbi68.VAL",m2))
        self.add_table_row("He gas farm (left, right)", val)
    
    def show_bmvac(self):
        self.table_entry_vac_title(("Component","Status", "Pressure CC (Pirani)", "Ion Pump Pressure (V,I)"))
        # BM A
        self.table_label_vac("13 BM A")
        self.add_pv("PA:13BM:Q01:00", desc = "Station Searched")
        self.vac_table("13BMA:ip1",label='Slit Tank',        type='GSE',  cc_pr=("13BMA",1))
        self.add_valve("13BMA:BMD_BS",'BMD White Beam Stop')
        self.add_valve("13BMA:BMC_BS",'BMC White Beam Stop')
        self.add_valve("13BMA:V1",'Valve 1')
        self.vac_table("13BMA:ip2",label='Mono Tank',        type='GSE',  cc_pr=("13BMA",2))
        self.add_valve("13BMA:V2",'Valve 2')
        self.vac_table("13BMA:ip1",label='Diagnostic Tank',   type='GSE',  cc_pr=("13BMA",3))
        self.add_valve("13BMA:V3",'Valve 3')

        # BM B
        self.table_label_vac("13 BM B")
        self.add_pv("PA:13BM:Q01:01", desc = "Station Searched")
        self.vac_table("13BMA:ip7",label='BMC Slit Tank',     type='GSE',  cc_pr=("13BMA",7))
        self.add_valve("13BMA:V4C",'BMC Valve 4')
        self.vac_table("13BMA:ip8",label='BMC Mono Tank',      type='GSE2',   cc_pr=("13BMA",8))
        self.add_mbbi("13BMA:eps_mbbi100.VAL")

        self.add_valve("13BMA:V4D",'BMD Valve 4')
        self.vac_table("13BMA:ip9",label='BMD Mirror Tank',   type='GSE2',  cc_pr=("13BMA",4))
        self.add_mbbi("13BMA:eps_mbbi99.VAL")

        # BM C
        self.table_label_vac("13 BM C")
        self.add_pv("PA:13BM:Q01:02", desc = "Station Searched")
        # BM D
        self.table_label_vac("13 BM D")
        self.add_pv("PA:13BM:Q01:03", desc = "Station Searched")
        self.vac_table("13BMA:ip10",label='BMD Slit Tank',
                       type='GSE',  cc_pr=("13BMA",9))
        self.vac_pirani("Flight Tube","13BMA:pr10")


    def show_idvac(self):
        self.table_entry_vac_title(("Component","Status",
                             "Pressure CC (Pirani)", "Ion Pump Pressure (V,I)"))
        # ID A
        self.table_label_vac("13 ID A")
        self.add_pv("PA:13ID:Q01:00", desc = "Station Searched")
        self.vac_table("FE:13:ID:IP7",label="Differential Pump",type='APS')

        self.add_valve("13IDA:V1",'Valve 1')
        self.vac_table("13IDA:ip1",label='Slit Tank',     type='GSE',  cc_pr=("13IDA",1))
        self.add_valve("13IDA:V2",'Valve 2')
        self.vac_table("13IDA:ip2",label='Mono Tank',     type='GSE2',  cc_pr=("13IDA",2))

        self.add_valve("13IDA:V3",'Valve 3')
        self.vac_table("13IDA:ip1",label='Pinhole Tank',  type='GSE',  cc_pr=("13IDA",3))

        self.add_valve("13IDA:BS",'White Beam Stop')
        self.add_valve("13IDA:V4",'Valve 4')
        self.vac_table("13IDA:ip3",label='Pumping Cross 1',     type='GSE')

        # ID B
        self.table_label_vac("13 ID B")
        self.add_pv("PA:13ID:Q01:01", desc = "Station Searched")
        self.vac_table("13IDA:ip5",label='Pumping Cross 2',    type='GSE',  cc_pr=("13IDA",5))
        self.add_valve("13IDA:V5",'Be Bypass #1')
        self.vac_table("13IDA:ip6",label='Vertical Mirror',    type='GSE2',  cc_pr=("13IDA",7))
        self.vac_table("13IDA:ip7",label='Horizontal  Mirror', type='GSE2')
        self.add_valve("13IDA:V6",'Be Bypass #2')

        self.vac_pirani("Flight Tube","13IDA:pr6")
        self.vac_pirani("BPM battery Voltage" ,  "13IDA:DMM2Ch9_raw.VAL",format = "%8.3f")

