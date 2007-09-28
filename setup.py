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

create_dir(config.cgi_bin,      desc='cgi_bin')
create_dir(config.logdir,       desc='log file')
create_dir(config.template_dir, desc='web template')

create_dir(config.data_dir,     desc='web data')
create_dir(config.jscal_dir,    desc='javascript calendar')

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


post_install = """
=================================================
Writing Apache configuration to httpd_pvarch.conf

You will need to edit Apache's configuration to
include this configuration.  (See httpd.conf)
=================================================

The next installation steps are:

  1. Run bin/pvarch_init_mysql to Initialize the
     MySQL tables for the archiver

  2. Start the caching and archiving processes:
        pvarch cache start
        pvarch start

  3. Add some PVs to the Archiver:
        pvarch add_pv 'XXX.VAL'
        
     Or edit a file listing PVs and add that:
        varch add_pvfile MyPVlist.txt

     See doc/Usage.txt for details.

  4. Edit the Web Status template files in
        %s
     read the README file, and run 'make'.
    
"""

print post_install % config.template_dir
# 
# print ""
# print "This requires having a "
# answer = raw_input('mysql username [%s]:' % super_user)
# print "Please run bin/pvarch_init_mysql"


