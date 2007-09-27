#!/usr/bin/env python
#
# setup script for PVArchiver.  Use    python setup.py install
#
import os
import sys
import shutil
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
    if len(config.dat_prefix)<2:       raise TypeError
    if len(config.cache_db)<2:         raise TypeError
except:
    print "Errors in config.py...."
    sys.exit(1)


def create_dir(dir,desc='?'):
    if not os.path.exists(dir):
        print 'Warning: %s directory %s does not exist.' % (desc,dir)
        print '         trying to create %s' % (dir)
        try:
            os.makedirs(dir)
        except OSError:
            print 'Error: could not create %s' % dir
            print 'perhaps you need more permission?'
    

shutil.copyfile('config.py','lib/config.py')

create_dir(config.cgi_bin, desc='cgi_bin')
create_dir(config.logdir,  desc='log file')
create_dir(config.status_dir, desc='web template')

httpdconf = """
#############################################
# apache configuration for Epics PV Archiver
# 
# include this in apache's httpd.conf

# 1. make sure the mod_python module is loaded.
#    See mod_python docs for more info

#LoadModule python_module modules/mod_python.so

# 2. specify directory for mod_python scripts
<Directory %s >
    AllowOverride FileInfo
    AddHandler mod_python .py
    PythonHandler mod_python.publisher
    PythonDebug  Off
</Directory>
#
# 3. restart apache.
#############################################
"""

f = open('httpd_pvarch.conf','w')
f.write(httpdconf % config.cgi_bin)
f.close()

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

print "================================================="
print "Writing Apache configuration to httpd_pvarch.conf"


