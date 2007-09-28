#!/usr/bin/env python

import time
from EpicsArchiver import Cache, util, config

pagetitle  = config.pagetitle
cgiroot    = config.cgi_url
footer     = config.footer
thispage   = "%s/status.py" % cgiroot
dblink     = "%s/archiver.py?pv=" % cgiroot


htmlhead = """<html>
<head><title>%s</title>
<meta http-equiv='Pragma'  content='no-cache'>
<meta http-equiv='Refresh' content=%s>
<style type='text/css'>
h4 {font: bold 18px verdana, arial, sans-serif;
    color: #044484; font-weight: bold; font-style: italic;}

body {margin: 20px; padding: 0px; background: #FCFCEA;
    font: bold 14px verdana, arial, sans-serif;}

#content {text-align: justify;  background: #FCFCEA;
    padding: 0px;  border: 4px solid #88000;
    border-top: none; z-index: 2;}

#tabmenu {font: bold 11px verdana, arial, sans-serif;
    border-bottom: 2px solid #880000;  margin: 1px;
    padding: 0px 0px 4px 0px; padding-left: 20px}

#tabmenu li {display: inline; overflow: hidden;
    margin: 1px; list-style-type: none; }

#tabmenu a, a.active {color: #4444AA; background: #EEDD88;
    border: 2px solid #880000; padding: 3px 3px 4px 3px;
    margin: 0px; text-decoration: none; }

#tabmenu a.active {color: #CC0000; background: #FCFCEA;
    border-bottom: 2px solid #FCFCEA;}

#tabmenu a:hover {color: #CC0000; background: #F9F9E0;}
</style></head>
<body><h4>%s&nbsp;&nbsp;&nbsp;&nbsp; %s</h4><ul id='tabmenu'>
""" 

class StatusWriter:
    table_def   = "<table width=90% cellpadding=1 border=0 cellspacing=2>"    
    hrule_row   = "<tr><td colspan=2> <hr>   </td></tr>"
    space_row   = "<tr><td colspan=2> &nbsp; </td></tr>"
    normal_row  = "<tr><td><b>%s</b></td><td>%s</td></tr>"
    colored_row = "<tr><td><b>%s</b></td><td><font color=%s> %s </font></td></tr>"
    title_row   = "<tr><th colspan=2><font color=%s>%s</font></tr>"
    
    def __init__(self,**args):
        self._cache    = Cache.Cache()
        self.pvget     = self._cache.get_full

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
        ret = self.pvget(pv,add=True)

        if ret == Cache.null_pv_value:
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
            try:
                rx = self.pvget(descpv,add=True)
                desc = rx['cvalue']
            except:
                pass
        if desc is None: desc = pv
        if outtype=='yes/no':
            oval = 'Unknown'
            if int(float(val.strip())) == 0: oval = 'No'
            if int(float(val.strip())) == 1: oval = 'Yes'
        return (desc,oval)

    def add_pv(self,pv,format=None,desc=None,type=None):    
        desc,val = self.get_pv(pv,format=format,desc=desc,outtype=type)
        self.linked_row(desc,pv,"%s" %val)

    def start_table(self,title=None):
        self.write("%s %s" %(self.table_def,self.table_space))
        if title:
            self.write(self.title_row % (self.titlecolor,title))

    def end_table(self):
        self.write("</table><br>")
            
    def linked_row(self,label,pvnames,vals):
        if isinstance(pvnames,(tuple,list)) and isinstance(vals,(tuple,list)):
            outlinks = []
            for name,val in zip(pvnames,vals):
                name = name.strip()
                if val is None: val = 'Unknown'
                outlinks.append( self.archlink(name,val))
            outval =  ',&nbsp; '.join(outlinks)
            if isinstance(label,(tuple,list)):
                label = ',&nbsp;'.join(label)

            self.row(label,outval)
        else:  # single pv/val:
            if vals is None: vals = 'Unknown'
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
            elif s.startswith('--'):
                self.write(self.hrule_row)
            elif s.startswith('<>'):
                self.write(self.space_row)
            else:
                cline = s.split('|')
                try:
                    pvnames = [i.strip() for i in cline.pop(0).strip().split(',')]
                except:
                    pvnames = []
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
                    if len(pvnames) == 1:
                        if desc is None: desc = labs[0]
                        self.linked_row(desc,pvnames[0],vals[0])
                    else:
                        if desc is None: desc = labs
                        self.linked_row(desc,pvnames,vals)

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
        self.write(htmlhead % (pagetitle, refresh, pagetitle, time.ctime()))
        for i in pagelist:
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

    ###
    ### Vacuum Tables: specialized to GSECARS-like vacuum system -- using a 4 column table...
    ### 
    def start_table_vac(self,title='Table'):
        self.write("%s %s" %(self.table_def,self.table_space))
        self.write("<tr><th colspan=4><font color=%s>%s</font></tr>" % (self.titlecolor,title))

    def vac_table(self,pv,cc_pr=(None,None), label=None,type='GSE'):
        ionpump_pvs  = {'GSE': ('_Volts.VAL','_Current.VAL','_Pressure.VAL'),
                        'GSE2':(':VOLT.VAL',':CUR.VAL',':PRES.VAL'),
                        'APS': ('.VOLT','.CRNT','.VAL') }


        tags = ionpump_pvs['GSE']
        if (self.ionpump_pvs.has_key(type)):  tags = ionpump_pvs[type]
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
        self.add_pv("PA:13BM:Q01:00.VAL", desc = "Station Searched")
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
        self.add_pv("PA:13BM:Q01:01.VAL", desc = "Station Searched")
        self.vac_table("13BMA:ip7",label='BMC Slit Tank',     type='GSE',  cc_pr=("13BMA",7))
        self.valve_row("13BMA:V4C",'BMC Valve 4')
        self.vac_table("13BMA:ip8",label='BMC Mono Tank',      type='GSE2',   cc_pr=("13BMA",8))
        self.add_pv("13BMA:eps_mbbi100.VAL")

        self.valve_row("13BMA:V4D",'BMD Valve 4')
        self.vac_table("13BMA:ip9",label='BMD Mirror Tank',   type='GSE2',  cc_pr=("13BMA",4))
        self.add_pv("13BMA:eps_mbbi99.VAL")

        # BM C
        self.table_label_vac("13 BM C")
        self.add_pv("PA:13BM:Q01:02.VAL", desc = "Station Searched")
        # BM D
        self.table_label_vac("13 BM D")
        self.add_pv("PA:13BM:Q01:03.VAL", desc = "Station Searched")
        self.vac_table("13BMA:ip10",label='BMD Slit Tank',
                       type='GSE',  cc_pr=("13BMA",9))
        self.vac_pirani("Flight Tube","13BMA:pr10.VAL")


    def show_idvac(self):
        self.table_entry_vac_title(("Component","Status",
                             "Pressure CC (Pirani)", "Ion Pump Pressure (V,I)"))
        # ID A
        self.table_label_vac("13 ID A")
        self.add_pv("PA:13ID:Q01:00.VAL", desc = "Station Searched")
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
        self.add_pv("PA:13ID:Q01:01.VAL", desc = "Station Searched")
        self.vac_table("13IDA:ip5",label='Pumping Cross 2',    type='GSE',  cc_pr=("13IDA",5))
        self.valve_row("13IDA:V5",'Be Bypass #1')
        self.vac_table("13IDA:ip6",label='Vertical Mirror',    type='GSE2',  cc_pr=("13IDA",7))
        self.vac_table("13IDA:ip7",label='Horizontal  Mirror', type='GSE2')
        self.valve_row("13IDA:V6",'Be Bypass #2')

        self.vac_pirani("Flight Tube","13IDA:pr6.VAL")
        self.vac_pirani("BPM battery Voltage" ,  "13IDA:DMM2Ch9_raw.VAL",format = "%8.3f")

            
