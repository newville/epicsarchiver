#!/usr/bin/env python

# reports motor settings now and at some earlier time

from EpicsArchiver import Archiver
from epics import caget
import time

tnow = time.time()
then = tnow - 3600*8.0

# change to your motor prefix
pv_base = '13BMD:m'


arch = Archiver()
suff ='VAL'
print  'PV      Old Val      Current Val     Description'
for i in range(1,20):
    pvname = "%s%i.%s" % (pv_base,i+1,suff)
    
    val_now  = arch.get_value_at_time(pvname, tnow)[1]
    val_then = arch.get_value_at_time(pvname, then)[1]
        
    desc  = caget( "%s%i.DESC" % (pv_base,i+1))
    print "%s  %15s %15s  %s" % (pvname, val_then, val_now,desc)
        
        
