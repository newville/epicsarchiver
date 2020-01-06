#!/usr/bin/env python
#
# setup script for PVArchiver.  Use    python setup.py install
#
import os
import sys
import shutil
import distutils
from distutils.core import setup
from distutils.dir_util import mkpath, copy_tree
#
try:
    import config
except:
    print("Error: cannot import config: Typo in config.py?")
    sys.exit(1)

try:
    import Gnuplot
except:
    pass
import epics
    
# This is useful for debugging / re-installing:
# a "full install" will mean that any running cache and 
# archiver will stop (abruptly -- the _mysql.so changes)
full_install = True
# full_install = False

script_name= sys.argv[0]
try:
    cmd  = sys.argv[1]
except:
    cmd = ''

def extract_mysqlso(tmpdir='.foo'):
    try:
        os.makedirs(tmpdir)
    except:
        pass
    l1 = os.listdir(tmpdir)
    os.environ['PYTHON_EGG_CACHE'] = tmpdir   
    import MySQLdb
    l2 = os.listdir(tmpdir)
    for i in l1: l2.remove(i)
    for i in l2:
        xdir  = os.path.join(tmpdir,i)
        xso   = os.path.join(xdir,'_mysql.so')        
        if os.path.isdir(xdir) and os.path.exists(xso):
            return xso

try: 
    x = config.dbpass[1:2].lower()
    if config.dbpass.lower().startswith('changethispassword'):
        raise TypeError('Forgot to change password ("dbpass" in config.py)!')
    if len(config.dbpass)<2:
        raise TypeError('Password too short ("dbpass" in config.py)!')
    if len(config.dat_prefix)<1:
        raise TypeError('Need a Data Table Prefix ("dat_prefix" in config.py)!')
except:
    xtype, errmsg, tb = sys.exc_info()
    print() 
    print("==  There were errors in config.py:")
    print("==  %s" % errmsg)

    sys.exit(1)
    

def create_dir(dir,desc='?'):
    if not os.path.exists(dir):
        print('Warning: %s directory %s does not exist.' % (desc,dir))
        print('         trying to create %s' % (dir))
        try:
            mkpath(dir)
        except OSError:
            print('Error: could not create %s' % dir)
            print('perhaps you need more permission?')
    

shutil.copyfile('config.py','lib/config.py')

if 'install' == cmd:
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
    SetHandler mod_python
    PythonHandler mod_python.publisher
    <Files ~ "\.(gif|html|jpg|png)$">
        SetHandler default-handler
    </Files>
    PythonDebug Off
</Directory>
#
# 3. restart apache.
#############################################
"""

f = open('httpd_pvarch.conf','w')
f.write(httpdconf % config.cgi_bin)
f.close()

bin_dir = os.path.join(sys.prefix,'bin')

# generate list of template files
template_files = []
for i in os.listdir('templates'):
    f = os.path.join('templates',i)
    if f.startswith('pages.py'): continue
    if os.path.isfile(f): template_files.append(f)


# generate list of web scripts:
cgifiles  = []
for i in os.listdir('cgi-bin'):
    f = os.path.join('cgi-bin',i)
    if f.endswith('.py') and os.path.isfile(f): cgifiles.append(f)

setup(
    name        = 'EpicsArchiver',
    version     = '1.2.0',
    author      = 'Matthew Newville',
    author_email= 'newville@cars.uchicago.edu',
    url         = 'http://millenia.cars.aps.anl.gov/~newville/Epics/PVArchiver/',
    license     = 'Python',
    script_name = script_name,
    description = 'A library for Archiving Epics PVs.',
    package_dir = {'EpicsArchiver': 'lib'},
    packages    = ['EpicsArchiver'], 
    data_files  = [(bin_dir, ['bin/pvarch']),
                   (config.cgi_bin, cgifiles),
                   (config.template_dir, template_files)
                   ]
    )

    


if 'install' == cmd:
    os.system("chmod -R 755 %s" %  (config.data_dir))
    if full_install:
        thisdir = os.getcwd()
        os.chdir(config.template_dir)
        os.system("touch FileList")
        os.system("make")
        os.chdir(thisdir)
        os.system("unzip -o jscalendar-1.0.zip")        
        copy_tree('jscalendar-1.0',   config.jscal_dir)

        mysqlso = extract_mysqlso('.foo')
        os.system("cp -pr %s %s/."  %  (mysqlso,config.share_dir))
        os.system("rm -rf .foo")

        setperms = "chown -R %s.%s" % (config.apache_user,config.apache_group)

        os.system("%s %s" % (setperms, config.data_dir))

        newso = os.path.join(config.share_dir, '_mysql.so')
        os.system("chmod 755 %s" %  (newso))
        os.system("%s %s" % (setperms, newso))

    
print("""=================================================
Writing Apache configuration to httpd_pvarch.conf

You will need to edit Apache's configuration to
include this configuration.  (See httpd.conf)
=================================================

Read INSTALL for the next installation steps.""")


# 
# print ""
# print "This requires having a "
# answer = raw_input('mysql username [%s]:' % super_user)
# print "Please run bin/pvarch_init_mysql"

x =  """The next installation steps are:

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

  5. View the web Status page at:
        %s/show/
  
 """ % (config.template_dir,config.cgi_bin)

