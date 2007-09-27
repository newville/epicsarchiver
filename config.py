#
# configuration file for PV_Archive.py

# here, give the mysql user name, password, and host
dbuser = 'epics'
dbpass = 'epics321'
dbhost = 'localhost'

# command for how mysql databases should be 'dumped'.
mysqldump = '/usr/bin/mysqldump --opt -p%s -u%s' % (dbpass,dbuser)

# location of log directories

#logdir = '/var/log/pvarch'
logdir = '/home/newville/Codes/Epics/pva/logs'


# location of python web scripts
cgi_bin  = '/usr/local/apache/cgi-bin/pvarch'

# how this maps to a URL:
cgi_url   = 'http://www.example.com/cgi-bin/pvarch'

data_dir  = '/usr/local/apache/cgi-data/pvarch'
data_url  = 'http://www.example.com/cgi-data/pvarch'

# location of editable web status template files
# the files in this directory should be readily editable
# to customize the PVs displayed in the status page
status_dir  = '/usr/local/apache/cgi-data/pvarch/web/'

# name of master database
master_db = 'zz_master'

# name of caching db
cache_db  = 'zz_cache'

# prefix used for sequentially named databases
# this *MUST* contain lowercase letters only
dat_prefix = 'pvdata'

# format string used for sequentially named databases
# please don't change this without care: the '_' is
# used to split the string, and a 5 digit number will
# allow enough unique databases.
dat_format = "%s_%.5i"




