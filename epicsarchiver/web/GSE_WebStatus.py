from .WebStatus import WebStatus

class GSEWebStatus(WebStatus):
    def __init__(self, cache=None, dbconn=None, **kws):
        WebStatus.__init__(self, cache=cache, dbconn=dbcon, **kws)
        
    def show_bmvac(self):
        self.table_entry_vac_title(("Component","Status", "Pressure CC (Pirani)", "Ion Pump Pressure (V,I)"))
        # BM A
        self.table_label_vac("13 BM A")
        self.show_pv("PA:13BM:Q01:00.VAL", desc = "Station Searched", type='yes/no')

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
        self.show_pv("PA:13BM:Q01:01.VAL", desc = "Station Searched", type='yes/no')
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
        self.show_pv("PA:13ID:STA_A_SRCHD_TO_B.VAL", desc = "Station Searched", type='yes/no')

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
        self.show_pv("PA:13ID:STA_B_SRCHD_TO_B.VAL", desc = "Station Searched", type='yes/no')        
        self.vac_table("13IDA:ip5",label='Pumping Cross 2',    type='GSE',  cc_pr=("13IDA",5))
        self.valve_row("13IDA:V5",'Be Bypass #1')
        self.vac_table("13IDA:ip6",label='Vertical Mirror',    type='GSE2',  cc_pr=("13IDA",7))
        self.vac_table("13IDA:ip7",label='Horizontal  Mirror', type='GSE2')
        self.valve_row("13IDA:V6",'Be Bypass #2')

        self.vac_pirani("Flight Tube","13IDA:pr6.VAL")
        self.vac_pirani("BPM battery Voltage" ,  "13IDA:DMM2Ch9_raw.VAL",format = "%8.3f")



    def show_idvac(self):
        self.table_entry_vac_title(("Component","Status",
                             "Pressure CC (Pirani)", "Ion Pump Pressure (V,I)"))
        # ID A
        self.table_label_vac("13 ID A")
        self.show_pv("PA:13ID:STA_A_SRCHD_TO_B.VAL", desc = "Station Searched", type='yes/no')

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
        self.show_pv("PA:13ID:STA_B_SRCHD_TO_B.VAL", desc = "Station Searched", type='yes/no')        
        self.vac_table("13IDA:ip5",label='Pumping Cross 2',    type='GSE',  cc_pr=("13IDA",5))
        self.valve_row("13IDA:V5",'Be Bypass #1')
        self.vac_table("13IDA:ip6",label='Vertical Mirror',    type='GSE2',  cc_pr=("13IDA",7))
        self.vac_table("13IDA:ip7",label='Horizontal  Mirror', type='GSE2')
        self.valve_row("13IDA:V6",'Be Bypass #2')

        self.vac_pirani("Flight Tube","13IDA:pr6.VAL")
        self.vac_pirani("BPM battery Voltage" ,  "13IDA:DMM2Ch9_raw.VAL",format = "%8.3f")
