#
# configuration file for PV_Archive.py

# here, give the mysql user name, password, and host
dbuser   = 'epics'
dbpass   = 'epics31234112'
dbhost   = 'localhost'


# command for how mysql databases should be 'dumped'.
mysqldump = '/usr/bin/mysqldump --opt -p%s -u%s' % (dbpass,dbuser)

# location of log directories
dblogdir = '/var/log/pvarch'

# location of python web scripts
cgi_bin = '/usr/local/apache/cgi-bin/pvarch'

# name of master database
masterdb = 'zz_master'

# name of caching db
cachedb  = 'zz_cache'

# prefix used for sequentially named databases
# this *MUST* contain lowercase letters only
dbprefix = 'pvdata'

# format string used for sequentially named databases
# please don't change this without care: the '_' is
# used to split the string, and a 5 digit number will
# allow enough unique databases.
dbformat = "%s_%.5i"




