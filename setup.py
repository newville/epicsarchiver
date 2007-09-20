#!/usr/bin/env python
#
# setup script for PVArchiver.  Use    python setup.py install
#
import os
import sys
import distutils
from distutils.core import setup
#
try:
    import config
except:
    print "Error: cannot import config: Typo in config.py?"
    sys.exit(1)

try: 
    x = config.dbpass[1:2].lower()
    if config.dbpass == 'Change Me!!': raise TypeError
    if len(config.dbpass)<3:           raise TypeError
    if len(config.dbprefix)<2:         raise TypeError
    if len(config.cachedb)<2:          raise TypeError
except:
    print "Errors in config.py...."
    sys.exit(1)


import shutil
shutil.copyfile('config.py','lib/config.py')

print 'ready for setup!'

bin_dir = os.path.join(sys.prefix,'bin')

setup(
    name        = 'EpicsArchiver',
    version     = '0.1',
    author      = 'Matthew Newville',
    author_email= 'newville@cars.uchicago.edu',
    license     = 'Python',
    description = 'A library for Archiving Epics PVs.',
    package_dir = {'EpicsArchiver': 'lib'},
    packages    = ['EpicsArchiver'],
    data_files  = [(bin_dir, ['bin/pvarch'])]
    # _init_mysql','pvarch'])]

)
