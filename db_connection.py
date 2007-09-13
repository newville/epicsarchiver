#
# configuration file for PV_Archive.py

#
# here, give the mysql user name, password, and host
dbuser   = 'epics'
dbpass   = 'epics'
dbhost   = 'localhost'

# command for how mysql databases should be 'dumped'.
mysqldump = '/usr/bin/mysqldump --opt -p%s -u%s' % (dbpass,dbuser)

# location of log directories
dblogdir = '/home/epics/logs'

# name of master database
masterdb = 'pvmain'

# name of caching db
cachedb  = 'pvtmp'

# prefix used for sequentially named databases
dbprefix = 'pvdata'


